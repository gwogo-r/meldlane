import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

import typer
import yaml

# Windows-консоль часто в cp1251 — форсируем UTF-8, иначе кириллица падает
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from agents.executor import execute_task
from capture.audio import record
from capture.transcriber import transcribe as whisper_transcribe
from config import settings
from metrics.capacity import compute_capacity
from models import Meeting, Member, Transcript, TranscriptSegment
from pipeline.extractor import extract_tasks
from storage.db import Storage

app = typer.Typer(
    add_completion=False,
    help="Meldlane — трекер для команд из людей и AI-агентов",
)


def load_team() -> list[Member]:
    data = yaml.safe_load(settings.team_path.read_text(encoding="utf-8"))
    return [Member(**m) for m in data["members"]]


def resolve_assignee(hint: str | None, members: list[Member]) -> str | None:
    if not hint:
        return None
    h = hint.strip().lower()
    for m in members:
        candidates = [m.id, m.name, *m.aliases]
        for c in candidates:
            c = c.lower()
            if h == c or h in c or c in h:
                return m.id
    return None


async def _members():
    storage = Storage()
    await storage.init()
    for m in load_team():
        await storage.upsert_member(m)

    for m in await storage.get_members():
        if m.kind.value == "agent":
            price = f"${m.price_in}/{m.price_out} за 1M ток."
            print(f"- [agent] {m.name} [{m.id}] — {m.provider}/{m.model} · {price}")
        else:
            cap = f"{m.capacity_sp} SP/нед" if m.capacity_sp else "—"
            print(f"- [human] {m.name} [{m.id}] — {m.role or ''} · {cap}")


async def _run_extraction(storage: Storage, meeting: Meeting, transcript: Transcript, members: list[Member]):
    """Общее ядро: transcript -> задачи -> сохранение -> печать. Используется extract и transcribe."""
    await storage.save_meeting(meeting)
    await storage.save_transcript(transcript)

    tasks, usage = await extract_tasks(transcript)
    await storage.add_token_usage(usage)
    await storage.clear_tasks(meeting.id)

    by_id = {m.id: m for m in members}
    for t in tasks:
        t.assignee_id = resolve_assignee(t.assignee_hint, members)
        await storage.add_task(t)

    print(f"митинг «{meeting.title}» [{meeting.id}] → задач: {len(tasks)}\n")
    for i, t in enumerate(tasks, 1):
        if t.assignee_id and t.assignee_id in by_id:
            who = by_id[t.assignee_id].name
        else:
            who = t.assignee_hint or "—"
        sp = f"{t.story_points} SP" if t.story_points else "—"
        print(f"{i}. {t.title}  ({sp} · → {who})")
        if t.evidence_quote:
            print(f"   «{t.evidence_quote}»")

    print(
        f"\nтокены: {usage.prompt_tokens}+{usage.completion_tokens}"
        f" = {usage.prompt_tokens + usage.completion_tokens}, стоимость: ${usage.cost_usd}"
    )


async def _load_members(storage: Storage) -> list[Member]:
    members = load_team()
    for m in members:
        await storage.upsert_member(m)
    return members


async def _capacity():
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)
    tasks = await storage.get_tasks()
    usage = await storage.get_token_usage()

    rows = compute_capacity(members, tasks, usage)
    if not rows:
        print("нет данных: сначала прогони extract/transcribe")
        return

    print(f"{'участник':<20}{'роль':<8}{'задач':<7}{'SP':<8}{'токены':<10}{'$ API':<12}{'$ подписка~':<14}")
    for r in rows:
        print(
            f"{r.name:<20}{r.kind:<8}{r.task_count:<7}{r.story_points:<8.1f}{r.tokens:<10}"
            f"{r.cost_usd_api:<12.4f}{r.cost_usd_subscription:<14.4f}"
        )
    print(
        "\n$ API — реальная оплата за токен (OpenRouter/OpenAI). "
        "$ подписка~ — cost-эквивалент под подпиской (Claude Pro/Max, ChatGPT), "
        "НЕ отдельный счёт, списывается из лимита подписки."
    )


async def _tasks():
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)
    by_id = {m.id: m for m in members}

    tasks = await storage.get_tasks()
    if not tasks:
        print("нет задач: сначала прогони extract/transcribe")
        return
    for t in tasks:
        who = by_id[t.assignee_id].name if t.assignee_id in by_id else (t.assignee_hint or "—")
        print(f"{t.id}  [{t.status.value:<16}] {t.title}  (-> {who})")


async def _run_task(task_id: str, no_confirm: bool):
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)
    by_id = {m.id: m for m in members}

    tasks = await storage.get_tasks()
    task = next((t for t in tasks if t.id == task_id), None)
    if task is None:
        print(f"задача {task_id} не найдена")
        return
    if not task.assignee_id or task.assignee_id not in by_id:
        print(f"у задачи «{task.title}» нет ассайни-агента")
        return
    agent = by_id[task.assignee_id]
    if agent.kind.value != "agent":
        print(f"«{agent.name}» — человек, AgentExecutor исполняет только задачи агентов")
        return

    print(f"[{agent.name}] планирую «{task.title}»...")
    updated, usage = await execute_task(task, agent, confirm=not no_confirm)
    await storage.add_token_usage(usage)
    await storage.add_task(updated)

    billing_label = "API (реальная оплата)" if usage.billing == "api" else "подписка (cost-эквивалент)"
    print(f"статус: {updated.status.value}")
    print(f"токены: {usage.prompt_tokens}+{usage.completion_tokens}, стоимость: ${usage.cost_usd} — {billing_label}")


async def _extract(path: Path, title: str):
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)

    text = path.read_text(encoding="utf-8")
    meeting = Meeting(id=uuid.uuid4().hex[:12], title=title, started_at=datetime.utcnow())
    transcript = Transcript(meeting_id=meeting.id, segments=[TranscriptSegment(text=text)])
    await _run_extraction(storage, meeting, transcript, members)


async def _capture(seconds: int, title: str):
    out_path = settings.out_dir / "recordings" / f"{uuid.uuid4().hex[:12]}.wav"
    print(f"запись {seconds} сек... (mic: {settings.mic_device or 'default'}, "
          f"system: {settings.system_audio_device or 'не сконфигурирован'})")
    record(out_path, seconds)
    print(f"записано: {out_path}")


async def _transcribe(wav_path: Path, title: str):
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)

    meeting = Meeting(id=uuid.uuid4().hex[:12], title=title, started_at=datetime.utcnow(), source="audio")
    print(f"транскрибирую {wav_path} (модель whisper: {settings.whisper_model})...")
    transcript = whisper_transcribe(wav_path, meeting.id)
    await _run_extraction(storage, meeting, transcript, members)


@app.command("members")
def members_cmd():
    """Показать состав команды (люди + агенты)."""
    asyncio.run(_members())


@app.command("extract")
def extract_cmd(
    transcript: Path = typer.Argument(..., help="путь к текстовому транскрипту"),
    title: str = typer.Option("Untitled meeting", help="название митинга"),
):
    """Извлечь задачи из текстового транскрипта митинга."""
    asyncio.run(_extract(transcript, title))


@app.command("tasks")
def tasks_cmd():
    """Показать все задачи с id, статусом и ассайни."""
    asyncio.run(_tasks())


@app.command("run-task")
def run_task_cmd(
    task_id: str = typer.Argument(..., help="id задачи (см. `python main.py tasks`)"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="пропустить ConfirmGate (для теста без Telegram)"),
):
    """Запустить AgentExecutor на задаче с ассайни-агентом."""
    asyncio.run(_run_task(task_id, no_confirm))


@app.command("capture")
def capture_cmd(
    seconds: int = typer.Option(30, help="длительность записи в секундах"),
    title: str = typer.Option("Untitled meeting", help="название митинга"),
):
    """Записать mic (+ system audio, если сконфигурирован VB-Cable) в WAV."""
    asyncio.run(_capture(seconds, title))


@app.command("transcribe")
def transcribe_cmd(
    wav: Path = typer.Argument(..., help="путь к WAV-записи"),
    title: str = typer.Option("Untitled meeting", help="название митинга"),
):
    """Транскрибировать WAV через Whisper и сразу извлечь задачи."""
    asyncio.run(_transcribe(wav, title))


@app.command("capacity")
def capacity_cmd():
    """Показать загрузку команды: люди в story points, агенты в токенах/$."""
    asyncio.run(_capacity())


if __name__ == "__main__":
    app()
