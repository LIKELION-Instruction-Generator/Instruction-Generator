#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

exec "${ROOT_DIR}/.venv_quizsvc/bin/python" -m streamlit run \
  src/stt_quiz_service/streamlit_app.py
