"""Синк Task -> issue в Plane.

Честная граница: Plane ожидает assignee = реальный аккаунт пользователя
workspace'а. У наших агентов (Claude Dev, Codex Dev, ...) таких аккаунтов
нет — "агент как equal assignee" в Plane не реализован, это по-прежнему
открытый архитектурный вопрос (см. ARCHITECTURE.md). Имя исполнителя,
SP и источник кладём в описание issue текстом, не в нативные поля Plane.

Идемпотентность — тот же паттерн, что в FeedbackOps/integrations/plane.py:
external_id (хэш от task.id) + external_source="meldlane", 409 на дубль
означает "уже есть", тогда PATCH существующей задачи вместо создания новой.
"""
import hashlib
import html

import httpx

from config import settings
from models import Member, Task

EXTERNAL_SOURCE = "meldlane"

# Task.status у нас шире, чем Plane group state, мапим на четыре стандартные группы Plane
STATUS_GROUP = {
    "todo": "unstarted",
    "in_progress": "started",
    "awaiting_confirm": "started",
    "testing": "started",
    "done": "completed",
    "blocked": "cancelled",
}


def _external_id(task: Task) -> str:
    return hashlib.sha256(task.id.encode()).hexdigest()[:32]


def _description(task: Task, assignee_name: str | None) -> str:
    esc = html.escape
    parts = [f"<p>{esc(task.description)}</p>" if task.description else ""]

    meta = [f"<strong>Источник:</strong> {esc(task.source.value)}"]
    if assignee_name:
        meta.append(f"<strong>Назначено:</strong> {esc(assignee_name)}")
    if task.story_points:
        meta.append(f"<strong>Story points:</strong> {task.story_points}")
    parts.append("<p>" + " · ".join(meta) + "</p>")

    if task.evidence_quote:
        parts.append(f"<blockquote>{esc(task.evidence_quote)}</blockquote>")
    return "".join(parts)


class PlaneConnector:
    def __init__(self):
        if not (settings.plane_base_url and settings.plane_api_token
                and settings.plane_workspace and settings.plane_project_id):
            raise RuntimeError(
                "Plane не сконфигурирован: заполни PLANE_BASE_URL, PLANE_API_TOKEN, "
                "PLANE_WORKSPACE, PLANE_PROJECT_ID в .env"
            )
        self.base_url = settings.plane_base_url.rstrip("/")
        self.headers = {"x-api-key": settings.plane_api_token, "Content-Type": "application/json"}

    def _issues_url(self, issue_id: str = "") -> str:
        base = (
            f"{self.base_url}/api/v1/workspaces/{settings.plane_workspace}"
            f"/projects/{settings.plane_project_id}/issues/"
        )
        return f"{base}{issue_id}/" if issue_id else base

    async def push(self, task: Task, assignee: Member | None = None) -> str:
        """Создаёт или обновляет issue для задачи. Возвращает Plane issue id."""
        external_id = _external_id(task)
        payload = {
            "name": task.title[:255],
            "description_html": _description(task, assignee.name if assignee else task.assignee_hint),
            "state": None,  # группа состояния зависит от default workflow проекта — не переопределяем
            "external_id": external_id,
            "external_source": EXTERNAL_SOURCE,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        async with httpx.AsyncClient(headers=self.headers, timeout=20) as client:
            resp = await client.post(self._issues_url(), json=payload)
            if resp.status_code == 409:
                existing_id = resp.json()["id"]
                resp = await client.patch(self._issues_url(existing_id), json=payload)
            if resp.status_code not in (200, 201):
                resp.raise_for_status()
            data = resp.json()
        return data["id"]
