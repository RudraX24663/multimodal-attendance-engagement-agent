#!/usr/bin/env bash
# One-step launcher for Mac/Linux: ./run.sh
set -e
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
python app.py
