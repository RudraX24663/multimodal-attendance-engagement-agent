"""Face detection, tracking and simple head-pose / movement signals (OpenCV only).

Head pose proxy: a frontal-face detection means the person faces the front;
a profile detection (either side) means they are looking away.
Upgrade path: swap `detect` for MediaPipe Face Mesh to get true yaw/pitch.
"""
import cv2
import numpy as np


class Detector:
    def __init__(self):
        d = cv2.data.haarcascades
        self.front = cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml")
        self.profile = cv2.CascadeClassifier(d + "haarcascade_profileface.xml")

    def detect(self, gray):
        """Return list of (x, y, w, h, facing_front)."""
        out = []
        for (x, y, w, h) in self.front.detectMultiScale(gray, 1.2, 5, minSize=(40, 40)):
            out.append((x, y, w, h, True))
        W = gray.shape[1]
        flipped = cv2.flip(gray, 1)
        for side, img in (("L", gray), ("R", flipped)):
            for (x, y, w, h) in self.profile.detectMultiScale(img, 1.2, 5, minSize=(40, 40)):
                if side == "R":
                    x = W - x - w
                cx, cy = x + w / 2, y + h / 2
                if not any(bx <= cx <= bx + bw and by <= cy <= by + bh for bx, by, bw, bh, _ in out):
                    out.append((x, y, w, h, False))
        return out


class CentroidTracker:
    """Greedy nearest-centroid tracker that keeps stable IDs across frames."""

    def __init__(self, max_dist: float, ttl_sec: float):
        self.max_dist, self.ttl = max_dist, ttl_sec
        self.tracks: dict[int, dict] = {}
        self.next_id = 1

    def update(self, dets, t):
        results, used = [], set()
        for (x, y, w, h, front) in dets:
            c = np.array([x + w / 2, y + h / 2])
            best, best_d = None, self.max_dist * w
            for pid, tr in self.tracks.items():
                if pid in used or t - tr["t"] > self.ttl:
                    continue
                d = float(np.linalg.norm(c - tr["c"]))
                if d < best_d:
                    best, best_d = pid, d
            if best is None:
                best, move = self.next_id, 0.0
                self.next_id += 1
            else:
                move = float(np.linalg.norm(c - self.tracks[best]["c"])) / w
            self.tracks[best] = {"c": c, "t": t}
            used.add(best)
            results.append({"t": t, "id": best, "facing": front, "move": move})
        return results


def analyze_video(path: str, cfg):
    """Return (samples, duration_sec). Each sample = one tracked face in one frame."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    step = max(1, round(fps / cfg.sample_fps))
    det, trk = Detector(), CentroidTracker(cfg.track_max_dist, cfg.track_ttl_sec)
    samples, idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            scale = 640 / frame.shape[1]
            if scale < 1:
                frame = cv2.resize(frame, None, fx=scale, fy=scale)
            gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            samples += trk.update(det.detect(gray), idx / fps)
        idx += 1
    cap.release()
    return samples, (total or idx) / fps
