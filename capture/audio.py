import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import settings

SAMPLE_RATE = 16_000  # Whisper ожидает 16kHz mono


def _find_device(name_hint: str | None, kind: str = "input") -> int | None:
    """Ищет устройство по подстроке имени. None -> системное дефолтное."""
    if not name_hint:
        return None
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        channels = d["max_input_channels"] if kind == "input" else d["max_output_channels"]
        if channels > 0 and name_hint.lower() in d["name"].lower():
            return i
    raise ValueError(f"аудио-устройство не найдено: {name_hint!r}")


def record(out_path: Path, seconds: int) -> Path:
    """Пишет mic (+ system audio через VB-Cable, если сконфигурирован) в один WAV.

    Без VB-Cable пишет только микрофон — этого достаточно, чтобы проверить
    конвейер целиком; system audio подключается, когда появится кабель.
    """
    mic_idx = _find_device(settings.mic_device, "input")
    sys_idx = _find_device(settings.system_audio_device, "input")

    mic_frames = sd.rec(
        int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=mic_idx
    )
    sys_frames = None
    if sys_idx is not None:
        sys_frames = sd.rec(
            int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=sys_idx
        )
    sd.wait()

    mixed = mic_frames
    if sys_frames is not None:
        # простое сложение с защитой от клиппинга через int32
        mixed = np.clip(mic_frames.astype(np.int32) + sys_frames.astype(np.int32), -32768, 32767).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(mixed.tobytes())
    return out_path
