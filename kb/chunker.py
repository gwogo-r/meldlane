"""Разбивка markdown-доков и python-кода на чанки для kb_chunks (MEL-009).

Markdown: чанк = один заголовок (любого уровня) + текст до следующего заголовка.
Python: чанк = один top-level def/class (через ast) + отдельный чанк "module" —
всё, что до первого def/class (импорты, докстринг модуля, константы).
"""
import ast
from pathlib import Path


def chunk_markdown(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    chunks: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in text.splitlines():
        if line.startswith("#"):
            if buf:
                chunks.append((heading, "\n".join(buf).strip()))
            heading = line.lstrip("#").strip()
            buf = [line]
        else:
            buf.append(line)
    if buf:
        chunks.append((heading, "\n".join(buf).strip()))
    return [(h, c) for h, c in chunks if c]


def chunk_python(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [("", text)] if text.strip() else []

    top_nodes = [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not top_nodes:
        return [("module", text)] if text.strip() else []

    chunks: list[tuple[str, str]] = []
    preamble = "\n".join(text.splitlines()[: top_nodes[0].lineno - 1]).strip()
    if preamble:
        chunks.append(("module", preamble))
    for node in top_nodes:
        segment = ast.get_source_segment(text, node) or ""
        if segment.strip():
            chunks.append((node.name, segment))
    return chunks
