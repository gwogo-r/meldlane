import json
import uuid

from llm_gateway import chat_completion, strip_code_fence

from config import settings
from models import Task, TaskSource, TokenUsage, Transcript

SYSTEM_PROMPT = """Ты ассистент, который превращает транскрипт рабочего митинга в список задач.
Извлеки конкретные, выполнимые задачи (action items) — то, что кто-то обязался сделать.

Часть задач достанется не человеку, а CLI-агенту с доступом к файловой системе (Claude
Code / Codex) — он выполняет то, что написано, буквально. Поэтому title и description
вместе должны читаться как прямая команда к исполнению, а не как протокол обсуждения.

Для каждой задачи верни объект:
- title: короткая формулировка в императиве, до 80 символов
- description: инструкция к исполнению в повелительном наклонении — что именно сделать.
  Если в обсуждении звучали конкретные файлы, функции, команды, эндпоинты — назови их
  прямо. Пиши "Добавь функцию X в Y, которая делает Z", а не "обсудили необходимость
  добавить функцию" — исполнитель не должен додумывать, что значит "обсудили"
- assignee_hint: имя человека или агента, на кого прозвучало назначение (или null)
- story_points: грубая оценка сложности из ряда 1,2,3,5,8 (или null)
- evidence_quote: дословная цитата из транскрипта, где задача прозвучала

Верни строго JSON-массив таких объектов. Если задач нет — верни [].
Не выдумывай задачи и назначения, которых не было в обсуждении."""


async def extract_tasks(transcript: Transcript) -> tuple[list[Task], TokenUsage]:
    text, usage = await chat_completion(
        system=SYSTEM_PROMPT,
        user=transcript.full_text[:16000],
        model=settings.llm_model_smart,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        price_in=settings.price_smart_in or 0.0,
        price_out=settings.price_smart_out or 0.0,
        stage="extractor",
    )

    raw = strip_code_fence(text or "[]")
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
