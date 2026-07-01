from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    text: str
    speaker: str | None = None
    start: float | None = None  # секунды от начала записи
    end: float | None = None


class Meeting(BaseModel):
    id: str
    title: str
    started_at: datetime
    source: str = "audio"  # audio | upload | live
    participants: list[str] = Field(default_factory=list)  # Member.id


class Transcript(BaseModel):
    meeting_id: str
    lang: str = "ru"
    segments: list[TranscriptSegment] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(s.text for s in self.segments)
