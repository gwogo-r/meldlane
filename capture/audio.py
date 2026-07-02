import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from config import settings

SAMPLE_RATE = 16_000  # целевая частота для Whisper (выход record() всегда 16kHz mono)


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


def _resample_to_target(frames: np.ndarray, native_rate: int) -> np.ndarray:
    """native_rate Hz, любое число каналов -> SAMPLE_RATE Hz mono int16."""
    if frames.shape[1] > 1:
        frames = frames.mean(axis=1, keepdims=True).astype(np.int16)
    if native_rate == SAMPLE_RATE:
        return frames
    resampled = resample_poly(frames[:, 0].astype(np.float64), SAMPLE_RATE, native_rate)
    return np.clip(resampled, -32768, 32767).astype(np.int16).reshape(-1, 1)


def _record_stream(device: int | None, seconds: float) -> np.ndarray:
    """Пишет seconds секунд с устройства через callback-API на его нативной частоте,
    возвращает SAMPLE_RATE Hz mono int16.

    Блокирующий sd.rec()/stream.read() не годится: WDM-KS устройства (напр.
    "Стерео микшер" — системный звук без VB-Cable) поддерживают только
    callback-режим (PaErrorCode -9999 на blocking read) и обычно работают
    на 48000 Hz, а не 16000 — открытие потока сразу на 16000 падает с
    "Invalid device". Пишем на нативной частоте устройства, ресемплим потом.
    """
    # sd.query_devices(None) возвращает список ВСЕХ устройств, а не дефолтное —
    # нужно сперва разрешить None в конкретный индекс через sd.default.device.
    resolved = device if device is not None else sd.default.device[0]
    info = sd.query_devices(resolved)
    native_rate = int(info["default_samplerate"])
    channels = min(info["max_input_channels"], 2) or 1

    frames: list[np.ndarray] = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=native_rate, channels=channels, dtype="int16", device=device, callback=callback):
        time.sleep(seconds)

    raw = np.concatenate(frames, axis=0) if frames else np.zeros((0, channels), dtype="int16")
    return _resample_to_target(raw, native_rate)


def record(out_path: Path, seconds: int) -> Path:
    """Пишет mic (+ system audio, если сконфигурирован) в один WAV, 16kHz mono.

    System audio: любое устройство-loopback — Windows "Стерео микшер" (штатный,
    без установки чего-либо, если включён в настройках звука) или VB-Cable,
    если поставлен. Без него пишет только микрофон.
    """
    mic_idx = _find_device(settings.mic_device, "input")
    sys_idx = _find_device(settings.system_audio_device, "input")

    if sys_idx is None:
        mixed = _record_stream(mic_idx, seconds)
    else:
        # два независимых потока в тредах — стартуют почти одновременно,
        # каждый ресемплится к SAMPLE_RATE независимо перед миксом
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            mic_future = pool.submit(_record_stream, mic_idx, seconds)
            sys_future = pool.submit(_record_stream, sys_idx, seconds)
            mic_frames = mic_future.result()
            sys_frames = sys_future.result()

        n = min(len(mic_frames), len(sys_frames))
        mixed = np.clip(
            mic_frames[:n].astype(np.int32) + sys_frames[:n].astype(np.int32), -32768, 32767
        ).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(mixed.tobytes())
    return out_path
