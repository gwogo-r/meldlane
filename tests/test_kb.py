import asyncio

import aiosqlite

from kb.chunker import chunk_markdown, chunk_python
from kb.index import search
from storage.db import Storage


def test_chunk_markdown_splits_by_heading(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\nintro\n## Section A\nbody a\n## Section B\nbody b\n", encoding="utf-8")

    chunks = chunk_markdown(p)

    assert [h for h, _ in chunks] == ["Title", "Section A", "Section B"]
    assert "body a" in chunks[1][1]
    assert "body b" in chunks[2][1]


def test_chunk_python_splits_top_level_defs(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text(
        "import os\n\n\ndef foo():\n    return 1\n\n\nclass Bar:\n    def baz(self):\n        pass\n",
        encoding="utf-8",
    )

    chunks = chunk_python(p)
    by_heading = dict(chunks)

    assert set(by_heading) == {"module", "foo", "Bar"}
    assert "import os" in by_heading["module"]
    assert "def foo" in by_heading["foo"]


def test_search_finds_inserted_chunk_by_bm25(tmp_path):
    storage = Storage(db_path=tmp_path / "kb_test.db")

    async def run():
        await storage.init()
        async with aiosqlite.connect(storage.db_path) as db:
            await db.execute(
                "INSERT INTO kb_chunks (path, heading, content) VALUES (?, ?, ?)",
                ("docs/example.md", "Example", "PlaneSink идемпотентность через external_source"),
            )
            await db.execute(
                "INSERT INTO kb_chunks (path, heading, content) VALUES (?, ?, ?)",
                ("docs/other.md", "Other", "совершенно не связанный текст про аудио захват"),
            )
            await db.commit()
        return await search(storage, "external_source", limit=5)

    results = asyncio.run(run())

    assert len(results) == 1
    assert results[0]["path"] == "docs/example.md"
