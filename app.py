"""Flask dashboard. Run: python app.py  ->  http://127.0.0.1:5000"""
import json
import os
import time

from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from src.config import Config
from src.live import LiveSession
from src.pipeline import REPORT_DIR, run
from src.sample import make_sample_report

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "data", "uploads")
app = Flask(__name__)
live = LiveSession()
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 ** 3


def load_report():
    path = os.path.join(REPORT_DIR, "latest.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return make_sample_report()


@app.get("/")
def index():
    return render_template("index.html", r=load_report(), error=request.args.get("error"))


@app.get("/api/report")
def api_report():
    return jsonify(load_report())


@app.get("/download/attendance.csv")
def download_csv():
    return send_from_directory(REPORT_DIR, "attendance.csv", as_attachment=True)


@app.post("/analyze")
def analyze():
    f = request.files.get("video")
    if not f or not f.filename:
        return redirect(url_for("index", error="Choose a video file first."))
    os.makedirs(UPLOADS, exist_ok=True)
    path = os.path.join(UPLOADS, secure_filename(f.filename))
    f.save(path)
    expected = request.form.get("expected", type=int)
    window = request.form.get("window", default=300, type=int)
    try:
        run(path, expected=expected, cfg=Config(window_sec=window, min_presence_sec=min(180, window)))
    except Exception as e:  # show a readable message instead of a stack trace
        return redirect(url_for("index", error=f"Could not analyse the video: {e}"))
    return redirect(url_for("index"))


@app.post("/live/start")
def live_start():
    window = request.form.get("window", default=60, type=int)
    presence = request.form.get("presence", default=20, type=int)
    try:
        live.start(Config(window_sec=window, min_presence_sec=presence), request.form.get("expected", type=int))
    except Exception as e:
        return jsonify(error=str(e))
    return jsonify(ok=True)


@app.post("/live/stop")
def live_stop():
    try:
        live.stop()
    except Exception as e:
        return jsonify(error=str(e))
    return jsonify(ok=True)


@app.get("/live/status")
def live_status():
    return jsonify(live.status())


@app.get("/video_feed")
def video_feed():
    def gen():
        while live.running:
            jpg = live.latest_jpeg()
            if jpg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.1)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    app.run(debug=False, threaded=True, host="127.0.0.1", port=5000)
