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


def _record_stream(device: int | None, frames_total: int) -> np.ndarray:
    """Читает frames_total сэмплов из устройства через собственный InputStream.

    Convenience-функция sd.rec() не годится для двух параллельных записей —
    rec/play делят один глобальный контекст, второй вызов глушит первый.
    """
    buf = np.empty((frames_total, 1), dtype="int16")
    filled = 0
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=device) as stream:
        while filled < frames_total:
            chunk, _ = stream.read(min(4096, frames_total - filled))
            n = len(chunk)
            buf[filled:filled + n] = chunk
            filled += n
    return buf


def record(out_path: Path, seconds: int) -> Path:
    """Пишет mic (+ system audio через VB-Cable, если сконфигурирован) в один WAV.

    Без VB-Cable пишет только микрофон — этого достаточно, чтобы проверить
    конвейер целиком; system audio подключается, когда появится кабель.
    """
    mic_idx = _find_device(settings.mic_device, "input")
    sys_idx = _find_device(settings.system_audio_device, "input")
    frames_total = int(seconds * SAMPLE_RATE)

    if sys_idx is None:
        mixed = _record_stream(mic_idx, frames_total)
    else:
        # два независимых потока в тредах — стартуют почти одновременно,
        # микшируются сложением с защитой от клиппинга
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            mic_future = pool.submit(_record_stream, mic_idx, frames_total)
            sys_future = pool.submit(_record_stream, sys_idx, frames_total)
            mic_frames = mic_future.result()
            sys_frames = sys_future.result()
        mixed = np.clip(
            mic_frames.astype(np.int32) + sys_frames.astype(np.int32), -32768, 32767
        ).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(mixed.tobytes())
    return out_path
