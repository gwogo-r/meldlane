from pathlib import Path

import whisper

from config import settings
from models import Transcript, TranscriptSegment

_model = None  # ленивая загрузка — тяжёлая модель нужна только при реальной транскрибации


def _get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(settings.whisper_model)
    return _model


def transcribe(wav_path: Path, meeting_id: str) -> Transcript:
    result = _get_model().transcribe(str(wav_path), language=settings.whisper_language)
    segments = [
        TranscriptSegment(text=s["text"].strip(), start=s["start"], end=s["end"])
        for s in result["segments"]
    ]
    return Transcript(meeting_id=meeting_id, lang=result.get("language", settings.whisper_language), segments=segments)
