"""AgentExecutor — доводит задачу с ассайни-агентом до статуса testing.

Два режима, по `Member.provider` в team.yaml:
  - provider="openrouter" — planning-only через Chat Completions API (без
    реального доступа к файлам/shell), платится по цене модели за токен.
  - provider="claude-code" / "codex" — реальное исполнение через CLI-агента
    (agents/cli_runner.py), списывается с подписки (Claude Pro/Max, ChatGPT
    Plus/Pro), не по цене за токен.

Цикл статусов одинаковый для обоих режимов:
  todo -> in_progress -> (ConfirmGate перед необратимым/реальным исполнением) ->
  awaiting_confirm -> testing (человек проверяет и переводит в done вручную)
"""
import json
import shutil

from openai import AsyncOpenAI

from agents.cli_runner import CliAgentError, run_claude_code, run_codex
from agents.confirm import ConfirmGate
from config import settings, BASE_DIR
from metrics.logger import usage_from_response
from models import Member, Task, TaskStatus, TokenUsage

# Что не копируем в рабочую копию для агента: git-история, кэши, БД, сами выводы агентов.
_WORKSPACE_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.db", "out", ".env", "node_modules", "*.wav"
)

PLAN_SYSTEM_PROMPT = """Ты AI-агент команды. Тебе назначена задача. Опиши план действий:
1-3 конкретных шага, что ты сделаешь. Если среди шагов есть необратимое действие
(деплой, отправка, запись во внешнюю систему) — отметь его явно.

Верни JSON: {"steps": ["...", "..."], "irreversible_step": "..." | null}"""

CLI_RUNNERS = {"claude-code": run_claude_code, "codex": run_codex}


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def select_effort(story_points: float | None) -> str:
    """Грубая сложность задачи -> уровень эффорта/модели. SP из TaskExtractor."""
    if not story_points or story_points <= 2:
        return "low"
    if story_points <= 5:
        return "medium"
    return "high"


async def plan_task(task: Task, agent: Member) -> tuple[dict, TokenUsage]:
    client = _client()
    response = await client.chat.completions.create(
        model=agent.model or settings.llm_model_smart,
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": f"{task.title}\n\n{task.description}"},
        ],
        temperature=0,
    )
    # Если агент не имеет цен, используем цены модели из settings
    price_in = agent.price_in or settings.price_smart_in
    price_out = agent.price_out or settings.price_smart_out
    usage = usage_from_response(
        response,
        stage="agent_plan",
        model=agent.model or settings.llm_model_smart,
        price_in=price_in,
        price_out=price_out,
        task_id=task.id,
        member_id=agent.id,
    )
    raw = (response.choices[0].message.content or "{}").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {"steps": [], "irreversible_step": None}
    return plan, usage


# claude-code: haiku/sonnet/opus по эффорту. codex: gpt-5.1 всегда, effort варьируется отдельным флагом.
_CLAUDE_MODEL_BY_EFFORT = {"low": "haiku", "medium": "sonnet", "high": "opus"}


def sync_workspace() -> None:
    """Свежая копия репозитория в out/agent_workspace/ перед каждым запуском.

    Агент должен видеть реальный код, чтобы задачи вроде "напиши тесты для X"
    были выполнимы, но не должен иметь доступа к боевому репозиторию — правит
    только копию. Копия перезаписывается с нуля на каждый запуск (детерминизм,
    без накопления мусора от прошлых попыток агента).
    """
    workspace = settings.agent_workspace_dir
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(BASE_DIR, workspace, ignore=_WORKSPACE_IGNORE)


async def _execute_via_cli(task: Task, agent: Member, *, confirm: bool) -> tuple[Task, TokenUsage]:
    task.status = TaskStatus.awaiting_confirm
    if confirm:
        gate = ConfirmGate()
        ok = await gate.ask(
            task.title, f"Реальное исполнение через {agent.provider} (доступ к файлам/shell). {task.description}"
        )
        if not ok:
            task.status = TaskStatus.blocked
            return task, TokenUsage(stage="agent_exec", model=agent.provider or "", cost_usd=0.0, task_id=task.id, member_id=agent.id)

    task.status = TaskStatus.in_progress
    effort = select_effort(task.story_points)
    prompt = f"{task.title}\n\n{task.description}".strip()

    workspace = settings.agent_workspace_dir
    sync_workspace()

    try:
        if agent.provider == "claude-code":
            _, usage = await run_claude_code(
                prompt, cwd=str(workspace), task_id=task.id, member_id=agent.id,
                model=_CLAUDE_MODEL_BY_EFFORT[effort],
            )
        else:  # codex
            _, usage = await run_codex(
                prompt, cwd=str(workspace), task_id=task.id, member_id=agent.id, effort=effort
            )
    except CliAgentError as e:
        # причину блокировки обязаны показать: молчаливый blocked уже прятал от нас
        # реальный баг (codex тихо терял --json и возвращал 0 токенов)
        print(f"[{agent.name}] исполнение сорвалось: {e}")
        task.status = TaskStatus.blocked
        return task, TokenUsage(stage="agent_exec_error", model=agent.provider or "", cost_usd=0.0, task_id=task.id, member_id=agent.id)

    task.status = TaskStatus.testing
    return task, usage


async def execute_task(task: Task, agent: Member, *, confirm: bool = True) -> tuple[Task, TokenUsage]:
    """Доводит задачу до `testing`, маршрутизируя по `agent.provider`.

    provider in CLI_RUNNERS -> реальное исполнение через CLI-агента (см. модуль docstring).
    иначе -> planning-only через OpenRouter (старое поведение, честная заглушка).

    Возвращает (Task с обновлённым статусом, TokenUsage) — вызывающая сторона
    отвечает за storage.add_token_usage(usage), как и extract_tasks.
    """
    if agent.provider in CLI_RUNNERS:
        return await _execute_via_cli(task, agent, confirm=confirm)

    task.status = TaskStatus.in_progress
    plan, usage = await plan_task(task, agent)

    if plan.get("irreversible_step"):
        task.status = TaskStatus.awaiting_confirm
        if confirm:
            gate = ConfirmGate()
            ok = await gate.ask(task.title, plan["irreversible_step"])
            if not ok:
                task.status = TaskStatus.blocked
                return task, usage

    # planning-only агент: реального исполнения нет, честно помечаем testing, не done.
    task.status = TaskStatus.testing
    return task, usage
