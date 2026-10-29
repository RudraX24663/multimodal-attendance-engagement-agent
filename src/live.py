"""Live session: webcam (OpenCV) + optional microphone (sounddevice) run in background threads."""
import threading
import time

import cv2
import numpy as np

from .attendance import AttendanceTracker
from .audio import speech_ratio_from_rms
from .config import Config
from .pipeline import build_report, save_report
from .vision import CentroidTracker, Detector

try:  # microphone is optional; the system falls back to video-only scoring
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None


class LiveSession:
    def __init__(self):
        self.running = False
        self._lock = threading.Lock()
        self._jpeg = None
        self._reset()

    def _reset(self):
        self.samples, self.rms, self.faces = [], [], 0
        self.cap = self.stream = self.thread = None
        self.cfg, self.expected, self.t0, self.mic = Config(), None, 0.0, False
        self.att = None

    def start(self, cfg: Config, expected=None, camera=0):
        if self.running:
            raise RuntimeError("A session is already running.")
        self._reset()
        cap = cv2.VideoCapture(camera)
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera. Close other apps using it and allow camera access.")
        self.cap, self.cfg, self.expected = cap, cfg, expected
        self.att = AttendanceTracker(cfg.min_presence_sec, cfg.gap_tolerance_sec)
        self._start_mic()
        self.t0 = time.time()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _start_mic(self):
        if sd is None:
            return
        try:
            def cb(indata, frames, t, status):
                self.rms.append(float(np.sqrt(np.mean(indata ** 2))))
            self.stream = sd.InputStream(channels=1, samplerate=16000, blocksize=480, callback=cb)  # 30 ms blocks
            self.stream.start()
            self.mic = True
        except Exception:
            self.stream, self.mic = None, False

    def _loop(self):
        det = Detector()
        trk = CentroidTracker(self.cfg.track_max_dist, self.cfg.track_ttl_sec)
        last_t, boxes = -1.0, []
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            t = time.time() - self.t0
            if t - last_t >= 1.0 / self.cfg.sample_fps:
                last_t = t
                scale = 640 / frame.shape[1]
                small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
                gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
                dets = det.detect(gray)
                res = trk.update(dets, t)
                for r in res:
                    self.att.update(r["id"], t)
                self.samples += res
                self.faces = len(dets)
                boxes = [(d, r["id"]) for d, r in zip(dets, res)]
                self._scale = scale if scale < 1 else 1.0
            sc = getattr(self, "_scale", 1.0)
            for (x, y, w, h, front), pid in boxes:
                p1, p2 = (int(x / sc), int(y / sc)), (int((x + w) / sc), int((y + h) / sc))
                col = (180, 140, 15) if front else (30, 100, 200)
                cv2.rectangle(frame, p1, p2, col, 2)
                cv2.putText(frame, f"Person {pid}", (p1[0], max(15, p1[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            ok2, buf = cv2.imencode(".jpg", frame)
            if ok2:
                with self._lock:
                    self._jpeg = buf.tobytes()
            time.sleep(0.03)

    def latest_jpeg(self):
        with self._lock:
            return self._jpeg

    def status(self):
        if not self.running:
            return {"running": False}
        present = sum(1 for r in self.att.records() if r["present"])
        return {"running": True, "elapsed": int(time.time() - self.t0), "faces": self.faces,
                "present": present, "mic": self.mic}

    def stop(self):
        if not self.running:
            raise RuntimeError("No session is running.")
        self.running = False
        duration = max(time.time() - self.t0, 1.0)
        self.thread.join(timeout=3)
        self.cap.release()
        if self.stream:
            self.stream.stop()
            self.stream.close()
        import math
        n_win = max(1, math.ceil(duration / self.cfg.window_sec))
        ratios = speech_ratio_from_rms(self.rms, self.cfg.window_sec, n_win) if len(self.rms) > 100 else None
        report = build_report(self.samples, duration, ratios, self.cfg, self.expected, "Live session", "webcam")
        save_report(report)
        with self._lock:
            self._jpeg = None
        return report
