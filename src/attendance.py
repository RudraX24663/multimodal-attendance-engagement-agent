"""Sustained-presence attendance: a person counts as present only after being
seen continuously (allowing short gaps) for `min_presence_sec`."""


class AttendanceTracker:
    def __init__(self, min_presence_sec: float, gap_tolerance_sec: float):
        self.min = min_presence_sec
        self.gap = gap_tolerance_sec
        self._runs: dict[int, list[list[float]]] = {}

    def update(self, pid: int, t: float) -> None:
        runs = self._runs.setdefault(pid, [])
        if runs and t - runs[-1][1] <= self.gap:
            runs[-1][1] = t
        else:
            runs.append([t, t])

    def records(self) -> list[dict]:
        out = []
        for pid, runs in sorted(self._runs.items()):
            sustained = [r for r in runs if r[1] - r[0] >= self.min]
            present = bool(sustained)
            out.append({
                "id": pid,
                "present": present,
                "first_seen_sec": sustained[0][0] if present else runs[0][0],
                "present_sec": sum(r[1] - r[0] for r in runs) if present else 0.0,
            })
        return out
