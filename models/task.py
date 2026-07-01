from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    awaiting_confirm = "awaiting_confirm"
    testing = "testing"
    done = "done"
    blocked = "blocked"


class TaskSource(str, Enum):
    meeting = "meeting"
    feedback = "feedback"
    manual = "manual"


class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    assignee_id: str | None = None  # Member.id — человек или агент, единая модель
    assignee_hint: str | None = None  # как назначение прозвучало в транскрипте
    status: TaskStatus = TaskStatus.todo
    story_points: float | None = None
    source: TaskSource = TaskSource.meeting
    source_ref: str | None = None  # meeting_id / feedback_id
    evidence_quote: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    plane_id: str | None = None  # id issue в Plane после синка
