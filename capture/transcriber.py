from pathlib import Path

from faster_whisper import WhisperModel

from config import settings
from models import Transcript, TranscriptSegment

_model: WhisperModel | None = None  # ленивая загрузка — модель нужна только при реальной транскрибации


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        # CTranslate2-бэкенд: в разы быстрее оригинального whisper на CPU при том
        # же качестве модели, не тянет torch (~450 МБ) как зависимость.
        _model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    return _model


def transcribe(wav_path: Path, meeting_id: str) -> Transcript:
    segments_iter, info = _get_model().transcribe(str(wav_path), language=settings.whisper_language)
    segments = [
        TranscriptSegment(text=s.text.strip(), start=s.start, end=s.end)
        for s in segments_iter
    ]
    return Transcript(meeting_id=meeting_id, lang=info.language or settings.whisper_language, segments=segments)
