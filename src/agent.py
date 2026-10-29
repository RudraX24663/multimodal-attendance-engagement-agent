"""Teaching-suggestion agent. Rule-based and fully offline: it reads the session
trends and writes plain-language tips. It supports decisions; it never enforces them."""


def _tip(title, detail, kind="idea"):
    return {"title": title, "detail": detail, "kind": kind}


def suggest(timeline, kpis, students, signals, duration_min):
    tips = []
    eng = [p["engagement"] for p in timeline]
    if len(eng) >= 3:
        low_i = min(range(len(eng)), key=eng.__getitem__)
        before = max(eng[:low_i + 1])
        if before - eng[low_i] >= 15:
            m = timeline[low_i]["minute"]
            tips.append(_tip(f"Add a break or quick poll near minute {m:g}",
                             f"Engagement fell from {before:.0f}% to {eng[low_i]:.0f}% before this point. "
                             "A short activity can reset attention."))
            after = eng[low_i + 1:]
            if after and max(after) - eng[low_i] >= 10:
                j = low_i + 1 + after.index(max(after))
                tips.append(_tip(f"Whatever you did near minute {timeline[j]['minute']:g} worked",
                                 f"Engagement recovered to {max(after):.0f}%. Consider repeating that format.", "good"))
    a = signals.get("audio")
    if a is not None and a < 0.4:
        tips.append(_tip("Use pair discussions after long explanations",
                         "Little speech activity was detected. Short discussions can raise participation."))
    if kpis["attendance_pct"] < 85:
        tips.append(_tip("Follow up on absences",
                         f"Attendance was {kpis['attendance_pct']:.0f}%. Check whether the time or format is a barrier."))
    late = [s for s in students if s["present"] and s["first_seen_sec"] > 0.1 * duration_min * 60]
    if late:
        tips.append(_tip(f"{len(late)} student(s) joined late",
                         "Consider a short recap at the start so latecomers can catch up."))
    avg = kpis["avg_engagement"]
    low = [s["name"] for s in students if s["present"] and s["engagement"] < avg - 20]
    if low:
        tips.append(_tip("Check in gently with " + ", ".join(low[:3]),
                         "Their engagement was well below the class average. This may reflect pacing, not the student."))
    if not tips:
        tips.append(_tip("The session looked steady",
                         "No major engagement dips or participation gaps were detected.", "good"))
    return tips
