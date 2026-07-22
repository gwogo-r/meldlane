import asyncio
import hashlib
import sys
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

# capture.* и agents.executor импортируются лениво внутри команд: whisper тянет
# torch (~4 сек), и холодный старт CLI доходил до 10+ сек даже на --help
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
            if m.price_in is not None:  # openrouter: цена за токен
                detail = f"{m.provider}/{m.model} · ${m.price_in}/{m.price_out} за 1M ток."
            else:  # cli-агент: списывается с подписки
                detail = f"{m.provider} CLI · подписка"
            print(f"- [agent] {m.name} [{m.id}] — {detail}")
        else:
            cap = f"{m.capacity_sp} SP/нед" if m.capacity_sp else "—"
            print(f"- [human] {m.name} [{m.id}] — {m.role or ''} · {cap}")


def _stable_meeting_id(source: Path) -> str:
    """meeting.id от пути источника, не случайный — повторный прогон того же файла
    переиспользует id, и clear_tasks() в _run_extraction реально чистит старые задачи
    вместо накопления дублей (MEL-023)."""
    return hashlib.sha256(str(source.resolve()).encode()).hexdigest()[:12]


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


async def _kb_index():
    from kb.index import build_index

    storage = Storage()
    await storage.init()
    n = await build_index(storage)
    print(f"проиндексировано чанков: {n}")


async def _kb_search(query: str, limit: int):
    from kb.index import search

    storage = Storage()
    await storage.init()
    results = await search(storage, query, limit=limit)
    if not results:
        print("ничего не найдено — если ещё не индексировал, прогони `kb-index`")
        return
    for r in results:
        heading = f" › {r['heading']}" if r["heading"] else ""
        snippet = " ".join(r["content"].split())[:280]
        print(f"\n[{r['path']}{heading}]\n  {snippet}...")


async def _sync_plane():
    from meldlane_tasks import PlaneSink

    storage = Storage()
    await storage.init()
    members = await _load_members(storage)
    by_id = {m.id: m for m in members}

    tasks = await storage.get_tasks()
    if not tasks:
        print("нет задач: сначала прогони extract/transcribe")
        return

    if not (settings.plane_base_url and settings.plane_api_token
            and settings.plane_workspace and settings.plane_project_id):
        print("Plane не сконфигурирован: заполни PLANE_BASE_URL, PLANE_API_TOKEN, "
              "PLANE_WORKSPACE, PLANE_PROJECT_ID в .env")
        return

    sink = PlaneSink(
        base_url=settings.plane_base_url,
        api_token=settings.plane_api_token,
        workspace=settings.plane_workspace,
        project_id=settings.plane_project_id,
        external_source="meldlane",
    )
    for t in tasks:
        assignee = by_id.get(t.assignee_id) if t.assignee_id else None
        # meldlane_tasks.PlaneSink дюк-тайпит по атрибутам Task (id/title/description/
        # source/story_points/evidence_quote совпадают дословно) — конвертация не нужна
        plane_id = await sink.push(t, assignee_name=assignee.name if assignee else None)
        t.plane_id = plane_id
        await storage.add_task(t)
        who = assignee.name if assignee else (t.assignee_hint or "—")
        print(f"{t.id}  ->  Plane #{plane_id[:8]}  «{t.title}»  (-> {who})")


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

    from agents.executor import execute_task

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
    meeting = Meeting(id=_stable_meeting_id(path), title=title, started_at=datetime.utcnow())
    transcript = Transcript(meeting_id=meeting.id, segments=[TranscriptSegment(text=text)])
    await _run_extraction(storage, meeting, transcript, members)


def _recordings_dir() -> Path:
    return settings.out_dir / "recordings"


async def _capture(seconds: int | None, title: str):
    from meldlane_transcribe.capture import MAX_SECONDS_DEFAULT, record_tracks, system_track_strategy
    from meldlane_transcribe.sessions import create_session_dir

    strategy = system_track_strategy()
    sys_label = {"wasapi-loopback": "WASAPI loopback", "named-device": "именованное устройство"}.get(
        strategy[0] if strategy else "", "нет — только микрофон"
    )
    session = create_session_dir(_recordings_dir())
    if seconds:
        print(f"запись {seconds} сек... (system: {sys_label})")
    else:
        print(f"запись начата (system: {sys_label}).\nОстанови из другого терминала: python main.py capture-stop")

    tracks = record_tracks(session, seconds or MAX_SECONDS_DEFAULT)
    print(f"записаны дорожки: {', '.join(tracks)} -> {session}")


async def _capture_stop():
    from meldlane_transcribe.capture import request_stop

    request_stop(_recordings_dir())
    print("сигнал остановки отправлен — идущая запись сохранится и завершится в течение ~1 сек")


# meldlane_transcribe.capture.record_tracks всегда называет дорожки так —
# см. capture.py в meldlane-transcribe (tracks["me"] = mic.wav, tracks["others"] = system.wav)
_SPEAKER_BY_FILENAME = {"mic.wav": "me", "system.wav": "others"}


async def _transcribe(source: Path, title: str):
    """source: WAV-файл ИЛИ папка сессии от `capture` (mic.wav [+ system.wav])."""
    from meldlane_transcribe import config as mt_config
    from meldlane_transcribe.models import merge_tracks as mt_merge_tracks
    from meldlane_transcribe.transcriber import transcribe_file

    storage = Storage()
    await storage.init()
    members = await _load_members(storage)

    meeting = Meeting(id=_stable_meeting_id(source), title=title, started_at=datetime.utcnow(), source="audio")
    wavs = (
        [(_SPEAKER_BY_FILENAME.get(p.name), p) for p in sorted(source.glob("*.wav"))]
        if source.is_dir()
        else [(None, source)]
    )

    print(f"транскрибирую {source} (модель: {mt_config.whisper_model()})...")
    tracks_segments, langs_by_segment_count = [], {}
    for speaker, wav in wavs:
        segments, track_lang, _ = transcribe_file(wav, speaker=speaker)
        tracks_segments.append(segments)
        if track_lang:
            langs_by_segment_count[track_lang] = langs_by_segment_count.get(track_lang, 0) + len(segments)
    # смешанные по языку встречи — не редкость (мик на одном языке, системный звук
    # на другом); берём язык дорожки с наибольшим числом сегментов, а не первой
    # попавшейся (раньше bug: mic.wav всегда обрабатывался первым по сортировке
    # имён и его язык побеждал независимо от того, где было больше речи)
    lang = max(langs_by_segment_count, key=langs_by_segment_count.get, default="")

    merged = mt_merge_tracks(*tracks_segments)
    transcript = Transcript(
        meeting_id=meeting.id,
        lang=lang,
        segments=[
            TranscriptSegment(text=s.text, speaker=s.speaker, start=s.start, end=s.end) for s in merged
        ],
    )
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


@app.command("sync-plane")
def sync_plane_cmd():
    """Синхронизировать локальные задачи в Plane (создать/обновить issue)."""
    asyncio.run(_sync_plane())


@app.command("kb-index")
def kb_index_cmd():
    """Проиндексировать markdown-доки и код проекта (FTS5) для kb-search."""
    asyncio.run(_kb_index())


@app.command("kb-search")
def kb_search_cmd(
    query: str = typer.Argument(..., help="поисковый запрос"),
    limit: int = typer.Option(5, help="сколько чанков показать"),
):
    """Полнотекстовый поиск по проиндексированным докам и коду."""
    asyncio.run(_kb_search(query, limit))


@app.command("run-task")
def run_task_cmd(
    task_id: str = typer.Argument(..., help="id задачи (см. `python main.py tasks`)"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="пропустить ConfirmGate (для теста без Telegram)"),
):
    """Запустить AgentExecutor на задаче с ассайни-агентом."""
    asyncio.run(_run_task(task_id, no_confirm))


@app.command("capture")
def capture_cmd(
    seconds: int | None = typer.Option(None, help="длительность записи в секундах; без флага — пишет, пока не остановишь через capture-stop"),
    title: str = typer.Option("Untitled meeting", help="название митинга"),
):
    """Записать mic (+ system audio, если найден loopback) раздельными дорожками через meldlane-transcribe."""
    asyncio.run(_capture(seconds, title))


@app.command("capture-stop")
def capture_stop_cmd():
    """Остановить идущую запись (запущенную без --seconds) из другого терминала."""
    asyncio.run(_capture_stop())


@app.command("transcribe")
def transcribe_cmd(
    source: Path = typer.Argument(..., help="WAV-файл или папка сессии от `capture` (mic.wav [+ system.wav])"),
    title: str = typer.Option("Untitled meeting", help="название митинга"),
):
    """Транскрибировать запись через meldlane-transcribe и сразу извлечь задачи."""
    asyncio.run(_transcribe(source, title))


@app.command("capacity")
def capacity_cmd():
    """Показать загрузку команды: люди в story points, агенты в токенах/$."""
    asyncio.run(_capacity())


if __name__ == "__main__":
    app()
