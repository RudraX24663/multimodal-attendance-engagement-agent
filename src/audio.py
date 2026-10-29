"""Audio activity detection using short-time energy (no cloud, no ML model)."""
import shutil
import subprocess
import wave

import numpy as np


def extract_audio(video_path: str, out_wav: str) -> bool:
    """Pull a mono 16 kHz WAV from a video using ffmpeg, if it is installed."""
    if not shutil.which("ffmpeg"):
        return False
    r = subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", out_wav],
                       capture_output=True)
    return r.returncode == 0


def speech_ratio_by_window(wav_path: str, window_sec: int, n_windows: int) -> list[float]:
    """Fraction of each window that contains speech-level energy (0..1)."""
    with wave.open(wav_path, "rb") as wf:
        sr, ch, width = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if width != 2:
        raise ValueError("Only 16-bit PCM WAV is supported")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    frame = int(0.03 * sr)
    n = len(x) // frame
    if n == 0:
        return [0.0] * n_windows
    rms = np.sqrt((x[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
    return speech_ratio_from_rms(rms, window_sec, n_windows)


def speech_ratio_from_rms(rms, window_sec: int, n_windows: int) -> list[float]:
    """rms = one energy value per 30 ms frame. Returns the speech share of each window."""
    rms = np.asarray(rms, dtype=np.float32)
    if rms.size == 0:
        return [0.0] * n_windows
    threshold = max(np.percentile(rms, 10) * 3.0, 0.005)  # adaptive to room noise
    voiced = rms > threshold
    per_win = int(window_sec / 0.03)
    return [float(voiced[i * per_win:(i + 1) * per_win].mean()) if len(voiced[i * per_win:(i + 1) * per_win]) else 0.0
            for i in range(n_windows)]
