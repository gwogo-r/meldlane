"""Запуск реальных coding-агентов (Claude Code / Codex CLI) как подпроцессов.

Идея: Meldlane не изобретает свой tool-use цикл, а оркестрирует уже существующие
CLI-агенты — они умеют читать/писать файлы, гонять shell, и это списывается
с подписки пользователя (Claude Pro/Max, ChatGPT Plus/Pro), а не по цене за токен
через platform API. Поэтому TokenUsage.cost_usd здесь берётся из JSON-вывода
самого агента (`total_cost_usd` у Claude Code), а не считается по прайсу модели.
"""
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from models import TokenUsage

# npm-глобальные бинарники (например codex) на Windows не всегда попадают в PATH
# процесса — добавляем типичное расположение как fallback перед тем, как сдаться.
_NPM_GLOBAL_FALLBACKS = [Path.home() / "AppData" / "Roaming" / "npm"]


class CliAgentError(RuntimeError):
    pass


def _find_binary(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    # На Windows пробуем .cmd/.exe раньше расширения без него — бинарник без
    # расширения в npm-папке обычно шелл-скрипт для WSL/git-bash, не Win32 exe.
    exts = (".cmd", ".exe", "") if sys.platform == "win32" else ("", ".cmd", ".exe")
    for d in _NPM_GLOBAL_FALLBACKS:
        for ext in exts:
            candidate = d / f"{name}{ext}"
            if candidate.exists():
                return str(candidate)
    raise CliAgentError(f"CLI-агент {name!r} не найден в PATH — установи и залогинься (`{name} login`)")


async def _run_subprocess(binary: str, args: list[str], cwd: str | None):
    """asyncio.create_subprocess_exec не умеет напрямую запускать .cmd/.bat на Windows
    (WinError 193) — такие скрипты (напр. codex.cmd от npm) нужно гнать через cmd /c."""
    if sys.platform == "win32" and binary.lower().endswith((".cmd", ".bat")):
        # CreateProcess не резолвит "cmd" через PATH сам по себе — нужен полный путь к cmd.exe.
        exe = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
        # cmd.exe рвёт командную строку на переносах строк даже внутри кавычек —
        # многострочный prompt (заголовок\n\nописание) обрезал --json и всё после
        # него, из-за чего codex тихо переключался на человеко-читаемый вывод
        # вместо NDJSON. Схлопываем переносы в аргументах перед сборкой команды.
        args = [a.replace("\r\n", " ").replace("\n", " ") if isinstance(a, str) else a for a in args]
        run_args = ["/c", binary, *args]
    else:
        exe = binary
        run_args = args
    return await asyncio.create_subprocess_exec(
        exe, *run_args,
        cwd=cwd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


# CLI-агент на сложной задаче может работать долго, но не бесконечно:
# без предела зависший процесс держит run-task вечно.
AGENT_TIMEOUT_SECONDS = 15 * 60


async def _communicate(proc, binary: str) -> tuple[bytes, bytes]:
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=AGENT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        raise CliAgentError(f"{binary}: превышен таймаут {AGENT_TIMEOUT_SECONDS} сек, процесс убит")


async def run_claude_code(prompt: str, *, cwd: str | None = None, task_id: str | None = None,
                           member_id: str | None = None, model: str | None = None) -> tuple[str, TokenUsage]:
    """Запускает `claude -p <prompt> --output-format json [--model ...]`, возвращает (текст, usage).

    model: sonnet | opus | haiku (или полное имя модели) — выбор по сложности
    задачи делает вызывающая сторона (executor.py), здесь просто прокидывается флагом.
    """
    binary = _find_binary("claude")
    args = ["-p", prompt, "--output-format", "json"]
    if model:
        args += ["--model", model]
    proc = await _run_subprocess(binary, args, cwd)
    stdout, stderr = await _communicate(proc, "claude")
    if proc.returncode != 0:
        raise CliAgentError(f"claude завершился с кодом {proc.returncode}: {stderr.decode(errors='replace')[:500]}")

    data = json.loads(stdout.decode(errors="replace"))
    usage_raw = data.get("usage", {})
    usage = TokenUsage(
        stage="agent_exec_claude_code",
        model="claude-code-cli",
        prompt_tokens=usage_raw.get("input_tokens", 0),
        completion_tokens=usage_raw.get("output_tokens", 0),
        cost_usd=data.get("total_cost_usd", 0.0),
        billing="subscription",
        task_id=task_id,
        member_id=member_id,
    )
    return data.get("result", ""), usage


async def run_codex(prompt: str, *, cwd: str | None = None, task_id: str | None = None,
                     member_id: str | None = None, model: str | None = None,
                     effort: str | None = None) -> tuple[str, TokenUsage]:
    """Запускает `codex exec <prompt> --json [--model ...] [-c model_reasoning_effort=...]`.

    effort: low | medium | high — выбор по сложности задачи делает executor.py.
    В отличие от Claude Code, вывод — поток NDJSON-событий (thread.started,
    turn.started, item.completed, turn.completed), не один JSON-объект.
    Текст ответа собирается из item.completed{type=agent_message}, токены —
    из turn.completed.usage. Codex по подписке ChatGPT не отдаёт $-стоимость
    (в отличие от total_cost_usd у Claude Code) — cost_usd всегда 0.0.
    """
    binary = _find_binary("codex")
    # По умолчанию codex exec работает в sandbox=read-only — не может писать файлы,
    # даже если модель сгенерировала правильный код (проверено: ответил текстом теста,
    # ничего не создал на диске). Раз мы всегда запускаем в изолированной копии
    # (executor.py -> sync_workspace()), безопасно разрешить запись в ней явно.
    args = ["exec", prompt, "--json", "--sandbox", "workspace-write"]
    if model:
        args += ["--model", model]
    if effort:
        args += ["-c", f"model_reasoning_effort={effort}"]
    proc = await _run_subprocess(binary, args, cwd)
    stdout, stderr = await _communicate(proc, "codex")
    if proc.returncode != 0:
        raise CliAgentError(f"codex завершился с кодом {proc.returncode}: {stderr.decode(errors='replace')[:500]}")

    text_parts = []
    prompt_tokens = completion_tokens = 0
    for line in stdout.decode(errors="replace").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            text_parts.append(event["item"].get("text", ""))
        elif event.get("type") == "turn.completed":
            u = event.get("usage", {})
            prompt_tokens = u.get("input_tokens", 0)
            completion_tokens = u.get("output_tokens", 0)

    usage = TokenUsage(
        stage="agent_exec_codex",
        model="codex-cli",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=0.0,
        billing="subscription",
        task_id=task_id,
        member_id=member_id,
    )
    return "\n".join(text_parts), usage


RUNNERS = {
    "claude-code": run_claude_code,
    "codex": run_codex,
}
