import aiosqlite

from config import settings
from models import Meeting, Member, Task, TokenUsage, Transcript

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcripts (
    meeting_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    assignee_id TEXT,
    source_ref TEXT,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    member_id TEXT,
    data TEXT NOT NULL
);

-- База знаний (MEL-009): FTS5 полнотекстовый индекс по markdown-докам и коду проекта.
-- Векторный поиск (sqlite-vec) — следующая итерация, нужен рабочий LLM-ключ для эмбеддингов.
CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks USING fts5(
    path UNINDEXED, heading UNINDEXED, content, tokenize='unicode61'
);
"""


class Storage:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.db_path

    async def init(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def upsert_member(self, m: Member):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO members (id, kind, data) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, data=excluded.data",
                (m.id, m.kind.value, m.model_dump_json()),
            )
            await db.commit()

    async def get_members(self, kind: str | None = None) -> list[Member]:
        async with aiosqlite.connect(self.db_path) as db:
            if kind:
                rows = await db.execute_fetchall(
                    "SELECT data FROM members WHERE kind = ?", (kind,)
                )
            else:
                rows = await db.execute_fetchall("SELECT data FROM members")
        return [Member.model_validate_json(row[0]) for row in rows]

    async def save_meeting(self, meeting: Meeting):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO meetings (id, data) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (meeting.id, meeting.model_dump_json()),
            )
            await db.commit()

    async def save_transcript(self, t: Transcript):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO transcripts (meeting_id, data) VALUES (?, ?) "
                "ON CONFLICT(meeting_id) DO UPDATE SET data=excluded.data",
                (t.meeting_id, t.model_dump_json()),
            )
            await db.commit()

    async def get_transcript(self, meeting_id: str) -> Transcript | None:
        async with aiosqlite.connect(self.db_path) as db:
            rows = await db.execute_fetchall(
                "SELECT data FROM transcripts WHERE meeting_id = ?", (meeting_id,)
            )
        return Transcript.model_validate_json(rows[0][0]) if rows else None

    async def add_task(self, task: Task):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO tasks (id, assignee_id, source_ref, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET assignee_id=excluded.assignee_id, "
                "source_ref=excluded.source_ref, data=excluded.data",
                (task.id, task.assignee_id, task.source_ref, task.model_dump_json()),
            )
            await db.commit()

    async def clear_tasks(self, source_ref: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM tasks WHERE source_ref = ?", (source_ref,))
            await db.commit()

    async def get_tasks(self, source_ref: str | None = None) -> list[Task]:
        async with aiosqlite.connect(self.db_path) as db:
            if source_ref:
                rows = await db.execute_fetchall(
                    "SELECT data FROM tasks WHERE source_ref = ?", (source_ref,)
                )
            else:
                rows = await db.execute_fetchall("SELECT data FROM tasks")
        return [Task.model_validate_json(row[0]) for row in rows]

    async def add_token_usage(self, usage: TokenUsage):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO token_usage (task_id, member_id, data) VALUES (?, ?, ?)",
                (usage.task_id, usage.member_id, usage.model_dump_json()),
            )
            await db.commit()

    async def get_token_usage(self) -> list[TokenUsage]:
        async with aiosqlite.connect(self.db_path) as db:
            rows = await db.execute_fetchall("SELECT data FROM token_usage")
        return [TokenUsage.model_validate_json(row[0]) for row in rows]
