import math
import struct
import wave

from src.agent import suggest
from src.attendance import AttendanceTracker
from src.config import Config
from src.fusion import fuse
from src.pipeline import build_report


def test_transient_face_is_not_present():
    t = AttendanceTracker(min_presence_sec=180, gap_tolerance_sec=10)
    for s in range(0, 20):
        t.update(1, s)
    assert not t.records()[0]["present"]


def test_sustained_presence_with_short_gap():
    t = AttendanceTracker(180, 10)
    for s in list(range(0, 100)) + list(range(105, 250)):
        t.update(1, s)
    r = t.records()[0]
    assert r["present"] and r["first_seen_sec"] == 0


def test_fusion_renormalises_without_audio():
    full = fuse({"head_pose": 1, "movement": 1, "activity": 1, "audio": 1})
    no_audio = fuse({"head_pose": 1, "movement": 1, "activity": 1, "audio": None})
    assert full == no_audio == 100.0


def test_fusion_clamps_and_empty():
    assert fuse({"head_pose": 5}) == 100.0
    assert fuse({}) == 0.0


def test_audio_speech_ratio(tmp_path):
    from src.audio import speech_ratio_by_window
    sr, p = 16000, str(tmp_path / "a.wav")
    frames = []
    for sec in range(20):  # first 10 s quiet noise, last 10 s loud tone
        for i in range(sr):
            v = 30 if sec < 10 else int(8000 * math.sin(2 * math.pi * 220 * i / sr))
            frames.append(struct.pack("<h", v))
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(frames))
    a, b = speech_ratio_by_window(p, 10, 2)
    assert a < 0.1 and b > 0.9


def test_agent_flags_dip():
    tl = [{"minute": i * 5, "engagement": e, "audio": 30} for i, e in enumerate([80, 78, 50, 70])]
    kp = {"attendance_pct": 100, "avg_engagement": 70}
    tips = suggest(tl, kp, [], {"audio": 0.5}, 20)
    assert any("minute 10" in t["title"] for t in tips)


def test_build_report_end_to_end():
    cfg = Config(window_sec=60, min_presence_sec=30)
    samples = [{"t": t / 2, "id": 1, "facing": True, "move": 0.1} for t in range(0, 240)]
    r = build_report(samples, 120, [0.5, 0.5], cfg, expected=2)
    assert r["kpis"]["present"] == 1 and r["kpis"]["total"] == 2
    assert r["kpis"]["attendance_pct"] == 50.0 and len(r["timeline"]) == 2


def test_speech_ratio_from_rms():
    from src.audio import speech_ratio_from_rms
    rms = [0.001] * 1000 + [0.2] * 1000          # 30 s quiet, 30 s loud (30 ms frames)
    a, b = speech_ratio_from_rms(rms, 30, 2)
    assert a < 0.1 and b > 0.9
