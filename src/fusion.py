"""Multimodal fusion: weighted average of visual and audio signals (each 0..1)."""

DEFAULT_WEIGHTS = {"head_pose": 0.40, "movement": 0.15, "activity": 0.20, "audio": 0.25}


def fuse(signals: dict, weights: dict | None = None) -> float:
    """Return an engagement score 0..100. Missing (None) signals are skipped and
    the remaining weights are renormalised, so the system works without audio."""
    w = weights or DEFAULT_WEIGHTS
    used = {k: v for k, v in signals.items() if v is not None and k in w}
    total = sum(w[k] for k in used)
    if total == 0:
        return 0.0
    score = sum(min(1.0, max(0.0, v)) * w[k] for k, v in used.items()) / total
    return round(100 * score, 1)
