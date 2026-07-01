import json
import uuid

from openai import AsyncOpenAI

from config import settings
from metrics.logger import usage_from_response
from models import Task, TaskSource, TokenUsage, Transcript

SYSTEM_PROMPT = """Ты ассистент, который превращает транскрипт рабочего митинга в список задач.
Извлеки конкретные, выполнимые задачи (action items) — то, что кто-то обязался сделать.

Для каждой задачи верни объект:
- title: короткая формулировка в императиве, до 80 символов
- description: что нужно сделать, детали из обсуждения
- assignee_hint: имя человека или агента, на кого прозвучало назначение (или null)
- story_points: грубая оценка сложности из ряда 1,2,3,5,8 (или null)
- evidence_quote: дословная цитата из транскрипта, где задача прозвучала

Верни строго JSON-массив таких объектов. Если задач нет — верни [].
Не выдумывай задачи и назначения, которых не было в обсуждении."""


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _strip_fence(raw: str) -> str:
    return (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )


async def extract_tasks(transcript: Transcript) -> tuple[list[Task], TokenUsage]:
    client = _client()
    response = await client.chat.completions.create(
        model=settings.llm_model_smart,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript.full_text[:16000]},
        ],
        temperature=0,
    )
    usage = usage_from_response(
        response,
        stage="extractor",
        model=settings.llm_model_smart,
        price_in=settings.price_smart_in or 0.0,
        price_out=settings.price_smart_out or 0.0,
    )

    raw = _strip_fence(response.choices[0].message.content or "[]")
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return [], usage

    tasks: list[Task] = []
    for item in items:
        try:
            tasks.append(
                Task(
                    id=uuid.uuid4().hex[:12],
                    title=item["title"],
                    description=item.get("description", ""),
                    assignee_hint=item.get("assignee_hint"),
                    story_points=item.get("story_points"),
                    source=TaskSource.meeting,
                    source_ref=transcript.meeting_id,
                    evidence_quote=item.get("evidence_quote", ""),
                )
            )
        except (KeyError, TypeError):
            continue
    return tasks, usage
