"""All tunable settings in one place."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    sample_fps: float = 2.0            # frames analysed per second of video
    window_sec: int = 300              # engagement window (5 minutes)
    min_presence_sec: float = 180.0    # sustained presence needed to mark attendance
    gap_tolerance_sec: float = 10.0    # short gaps (blinks, turns) don't break presence
    track_max_dist: float = 1.5        # max centroid jump, in face widths, to keep an ID
    track_ttl_sec: float = 5.0         # forget a face after this long unseen
    still_move_thresh: float = 0.02    # movement (face widths/sample) below this = still
    speech_full_score_ratio: float = 0.5  # 50% speech in a window = full audio score
    weights: dict = field(default_factory=lambda: {
        "head_pose": 0.40, "movement": 0.15, "activity": 0.20, "audio": 0.25})
