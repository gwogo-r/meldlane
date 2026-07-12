"""Read-only web API поверх того же Storage, что использует CLI (main.py tasks/capacity).

MVP (MEL-022/MEL-008): просмотр задач и загрузки команды в браузере, без auth —
single-user, как и сам CLI сейчас. Запуск: uvicorn api.app:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import _load_members
from metrics.capacity import compute_capacity
from storage.db import Storage

app = FastAPI(title="Meldlane API")

# Vite dev server по умолчанию на 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


class TaskOut(BaseModel):
    id: str
    title: str
    status: str
    story_points: float | None
    assignee: str
    plane_id: str | None = None


class CapacityOut(BaseModel):
    member_id: str
    name: str
    kind: str
    story_points: float
    task_count: int
    tokens: int
    cost_usd_api: float
    cost_usd_subscription: float


@app.get("/api/tasks", response_model=list[TaskOut])
async def get_tasks():
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)
    by_id = {m.id: m for m in members}

    tasks = await storage.get_tasks()
    return [
        TaskOut(
            id=t.id,
            title=t.title,
            status=t.status.value,
            story_points=t.story_points,
            assignee=by_id[t.assignee_id].name if t.assignee_id in by_id else (t.assignee_hint or "—"),
            plane_id=t.plane_id,
        )
        for t in tasks
    ]


@app.get("/api/capacity", response_model=list[CapacityOut])
async def get_capacity():
    storage = Storage()
    await storage.init()
    members = await _load_members(storage)
    tasks = await storage.get_tasks()
    usage = await storage.get_token_usage()

    rows = compute_capacity(members, tasks, usage)
    return [CapacityOut(**r.model_dump()) for r in rows]
