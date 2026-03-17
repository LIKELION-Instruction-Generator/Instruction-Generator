#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

DATABASE_URL="$("${ROOT_DIR}/.venv_quizsvc/bin/python" - <<'PY'
from stt_quiz_service.config import load_settings
print(load_settings().database_url)
PY
)"

if [[ "${DATABASE_URL}" == postgresql* ]]; then
  "${ROOT_DIR}/scripts/start_postgres.sh"
fi

if [[ "${STT_QUIZ_SYNC_ACCEPTED_WEEKLY_BASELINE:-true}" == "true" ]]; then
  "${ROOT_DIR}/.venv_quizsvc/bin/python" "${ROOT_DIR}/scripts/sync_weekly_read_model.py" --week-id 1
fi

UVICORN_ARGS=(
  stt_quiz_service.api.app:create_app
  --factory
)

if [[ "${STT_QUIZ_RELOAD:-false}" == "true" ]]; then
  UVICORN_ARGS+=(--reload)
fi

exec "${ROOT_DIR}/.venv_quizsvc/bin/python" -m uvicorn "${UVICORN_ARGS[@]}"
