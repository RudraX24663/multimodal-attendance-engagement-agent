"""End-to-end pipeline: video (+audio) -> attendance, engagement, suggestions -> report."""
import argparse
import csv
import json
import math
import os
import tempfile
from collections import defaultdict
from datetime import datetime
from statistics import mean

from .agent import suggest
from .attendance import AttendanceTracker
from .config import Config
from .fusion import fuse

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports")


def fmt_time(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def build_report(samples, duration_sec, audio_ratios, cfg: Config, expected=None, title="Session", source=""):
    tracker = AttendanceTracker(cfg.min_presence_sec, cfg.gap_tolerance_sec)
    for s in samples:
        tracker.update(s["id"], s["t"])
    records = tracker.records()
    present_ids = {r["id"] for r in records if r["present"]}
    n_win = max(1, math.ceil(duration_sec / cfg.window_sec))

    by_win = defaultdict(lambda: defaultdict(list))
    for s in samples:
        if s["id"] in present_ids:
            by_win[min(int(s["t"] // cfg.window_sec), n_win - 1)][s["id"]].append(s)

    timeline, per_student = [], defaultdict(list)
    acc = defaultdict(list)
    for w in range(n_win):
        if not by_win[w]:
            continue
        ratio = None if audio_ratios is None else audio_ratios[w]
        audio = None if ratio is None else min(1.0, ratio / cfg.speech_full_score_ratio)
        scores = []
        for pid, ss in by_win[w].items():
            sig = {
                "head_pose": mean(1.0 if x["facing"] else 0.0 for x in ss),
                "movement": 1 - min(1.0, mean(x["move"] for x in ss) / 0.5),
                "activity": 1 - mean(1.0 if x["move"] < cfg.still_move_thresh else 0.0 for x in ss),
                "audio": audio,
            }
            for k, v in sig.items():
                if v is not None:
                    acc[k].append(v)
            sc = fuse(sig, cfg.weights)
            scores.append(sc)
            per_student[pid].append(sc)
        timeline.append({"minute": round(w * cfg.window_sec / 60, 1),
                         "engagement": round(mean(scores), 1),
                         "audio": None if ratio is None else round(100 * ratio)})

    # longest stretch without movement
    longest, who = 0.0, "-"
    for pid in present_ids:
        run_start = None
        for s in sorted((x for x in samples if x["id"] == pid), key=lambda x: x["t"]):
            if s["move"] < cfg.still_move_thresh:
                run_start = s["t"] if run_start is None else run_start
                if s["t"] - run_start > longest:
                    longest, who = s["t"] - run_start, f"Person {pid}"
            else:
                run_start = None

    students = []
    for r in records:
        if r["present"]:
            students.append({"name": f"Person {r['id']}", "present": True,
                             "first_seen": fmt_time(r["first_seen_sec"]), "first_seen_sec": r["first_seen_sec"],
                             "present_min": round(r["present_sec"] / 60, 1),
                             "engagement": round(mean(per_student[r["id"]]), 1) if per_student[r["id"]] else 0})
    present = len(students)
    total = max(expected or 0, present) or 1
    speech_min = None
    if audio_ratios is not None:
        speech_min = round(sum(r * cfg.window_sec for r in audio_ratios) / 60, 1)
    avg_eng = round(mean(p["engagement"] for p in timeline), 1) if timeline else 0.0
    kpis = {"present": present, "total": total, "attendance_pct": round(100 * present / total, 1),
            "avg_engagement": avg_eng, "speech_min": speech_min,
            "longest_still_min": round(longest / 60, 1), "longest_still_who": who}
    signals = {k: (round(mean(acc[k]), 2) if acc[k] else None)
               for k in ("head_pose", "movement", "activity", "audio")}
    return {"session": {"title": title, "duration_min": round(duration_sec / 60, 1), "source": source,
                        "generated": datetime.now().strftime("%Y-%m-%d %H:%M")},
            "kpis": kpis, "timeline": timeline, "students": students, "signals": signals,
            "suggestions": suggest(timeline, kpis, students, signals, duration_sec / 60)}


def save_report(report, out_dir=REPORT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out_dir, "attendance.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["student", "status", "first_seen", "minutes_present", "engagement_pct"])
        for s in report["students"]:
            w.writerow([s["name"], "Present", s["first_seen"], s["present_min"], s["engagement"]])


def run(video, audio=None, expected=None, title="Classroom session", cfg: Config | None = None, out_dir=REPORT_DIR):
    from .audio import extract_audio, speech_ratio_by_window  # lazy: keeps tests light
    from .vision import analyze_video
    cfg = cfg or Config()
    samples, duration = analyze_video(video, cfg)
    n_win = max(1, math.ceil(duration / cfg.window_sec))
    ratios = None
    wav = audio
    if wav is None:
        tmp = os.path.join(tempfile.gettempdir(), "session_audio.wav")
        wav = tmp if extract_audio(video, tmp) else None
    if wav:
        ratios = speech_ratio_by_window(wav, cfg.window_sec, n_win)
    report = build_report(samples, duration, ratios, cfg, expected, title, os.path.basename(video))
    save_report(report, out_dir)
    return report


def main():
    ap = argparse.ArgumentParser(description="Analyse a classroom recording.")
    ap.add_argument("--video", required=True)
    ap.add_argument("--audio", help="optional 16-bit WAV; otherwise extracted from the video with ffmpeg")
    ap.add_argument("--expected", type=int, help="class size, used for attendance %%")
    ap.add_argument("--window-sec", type=int, default=300)
    ap.add_argument("--min-presence-sec", type=float, default=180)
    a = ap.parse_args()
    cfg = Config(window_sec=a.window_sec, min_presence_sec=a.min_presence_sec)
    r = run(a.video, a.audio, a.expected, cfg=cfg)
    print(f"Done: {r['kpis']['present']}/{r['kpis']['total']} present, "
          f"average engagement {r['kpis']['avg_engagement']}%. Open the dashboard with: python app.py")


if __name__ == "__main__":
    main()
