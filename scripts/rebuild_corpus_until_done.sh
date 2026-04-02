#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/artifacts/pipeline_state"
RUN_LOG="$LOG_DIR/rebuild_full.log"
SUPERVISOR_LOG="$LOG_DIR/rebuild_supervisor.log"

mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] supervisor start" >> "$SUPERVISOR_LOG"

while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] run start" >> "$SUPERVISOR_LOG"
  if ./.venv_quizsvc/bin/python -u scripts/rebuild_corpus_full.py >> "$RUN_LOG" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] run success" >> "$SUPERVISOR_LOG"
    exit 0
  fi
  status=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] run failed exit_code=$status retry_in=15s" >> "$SUPERVISOR_LOG"
  sleep 15
done
