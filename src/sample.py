"""Built-in demo data so the dashboard works before you analyse a real video."""
from .agent import suggest


def make_sample_report():
    eng = [72, 78, 81, 76, 69, 58, 49, 54, 66, 74, 80, 77]
    audio = [30, 35, 40, 25, 20, 18, 15, 20, 45, 40, 35, 30]
    timeline = [{"minute": i * 5, "engagement": e, "audio": a} for i, (e, a) in enumerate(zip(eng, audio))]
    rows = [("Person 1", "00:02:10", 58, 84), ("Person 2", "00:01:05", 60, 79), ("Person 3", "00:04:00", 55, 88),
            ("Person 4", "00:03:20", 57, 52), ("Person 5", "00:12:30", 46, 71), ("Person 6", "00:02:00", 60, 76),
            ("Person 7", "00:05:10", 53, 81)]
    students = [{"name": n, "present": True, "first_seen": f, "first_seen_sec": 0, "present_min": m, "engagement": e}
                for n, f, m, e in rows]
    students[4]["first_seen_sec"] = 750
    kpis = {"present": 7, "total": 8, "attendance_pct": 87.5, "avg_engagement": round(sum(eng) / len(eng), 1),
            "speech_min": 18.0, "longest_still_min": 6.0, "longest_still_who": "Person 4"}
    signals = {"head_pose": 0.74, "movement": 0.68, "activity": 0.81, "audio": 0.52}
    return {"session": {"title": "Sample session (demo data)", "duration_min": 60, "source": "built-in sample",
                        "generated": "-"},
            "kpis": kpis, "timeline": timeline, "students": students, "signals": signals,
            "suggestions": suggest(timeline, kpis, students, signals, 60), "is_sample": True}
