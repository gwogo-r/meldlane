"""Индексация и поиск по базе знаний (MEL-009): FTS5 по markdown-докам + коду проекта.

AnythingLLM как ядро сознательно не используется (см. PLAN.md, "База знаний") —
гибрид FTS5+sqlite-vec, ноль внешних серверов. Векторная половина (sqlite-vec)
пока не подключена: нужен рабочий LLM-ключ для генерации эмбеддингов, которого
в этой среде сейчас нет (см. backlog MEL-009).
"""
import re

import aiosqlite

from config import BASE_DIR
from kb.chunker import chunk_markdown, chunk_python
from storage.db import Storage

_PY_SOURCE_DIRS = ["models", "pipeline", "agents", "metrics", "storage", "api", "kb", "tests"]
_PY_ROOT_FILES = ["main.py", "config.py"]
_SKIP_DIR_NAMES = {"__pycache__", "node_modules", "dist", "out", ".git"}


def _markdown_files() -> list:
    return sorted(p for p in BASE_DIR.glob("*.md") if p.is_file())


def _python_files() -> list:
    files = [BASE_DIR / f for f in _PY_ROOT_FILES if (BASE_DIR / f).exists()]
    for dirname in _PY_SOURCE_DIRS:
        d = BASE_DIR / dirname
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            if not any(part in _SKIP_DIR_NAMES for part in p.parts):
                files.append(p)
    return sorted(files)


async def build_index(storage: Storage) -> int:
    count = 0
    async with aiosqlite.connect(storage.db_path) as db:
        await db.execute("DELETE FROM kb_chunks")

        for path in _markdown_files():
            rel = str(path.relative_to(BASE_DIR))
            for heading, content in chunk_markdown(path):
                await db.execute(
                    "INSERT INTO kb_chunks (path, heading, content) VALUES (?, ?, ?)",
                    (rel, heading, content),
                )
                count += 1

        for path in _python_files():
            rel = str(path.relative_to(BASE_DIR))
            for heading, content in chunk_python(path):
                await db.execute(
                    "INSERT INTO kb_chunks (path, heading, content) VALUES (?, ?, ?)",
                    (rel, heading, content),
                )
                count += 1

        await db.commit()
    return count


def _fts_query(text: str) -> str:
    """Свободный пользовательский ввод -> безопасный FTS5-запрос.

    Голые термины через пробел в FTS5 по умолчанию AND'ятся; кавычки защищают
    от того, что дефисы/спецсимволы в вводе (например "MEL-016") сломают
    синтаксис запроса (дефис перед термином — оператор исключения в FTS5).
    """
    terms = re.findall(r"\w+", text, flags=re.UNICODE)
    if not terms:
        return '""'
    return " ".join(f'"{t}"' for t in terms)


async def search(storage: Storage, query: str, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(storage.db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT path, heading, content, bm25(kb_chunks) AS score FROM kb_chunks "
            "WHERE kb_chunks MATCH ? ORDER BY score LIMIT ?",
            (_fts_query(query), limit),
        )
    return [dict(r) for r in rows]
