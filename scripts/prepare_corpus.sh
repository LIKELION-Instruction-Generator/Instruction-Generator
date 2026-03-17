#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

API_URL="${STT_QUIZ_API_URL:-http://127.0.0.1:8000}"
TRANSCRIPTS_ROOT="${STT_QUIZ_TRANSCRIPTS_ROOT:-NLP_Task2/강의 스크립트}"
CURRICULUM_PATH="${STT_QUIZ_CURRICULUM_PATH:-NLP_Task2/강의 커리큘럼.csv}"
OUTPUT_DIR="${STT_QUIZ_PREPARED_OUTPUT_DIR:-artifacts/preprocessed}"
PERSIST_TO_DB="${STT_QUIZ_PREPARE_PERSIST_TO_DB:-true}"
PREPROCESS_MODEL_OVERRIDE="${STT_QUIZ_PREPROCESS_MODEL_OVERRIDE:-}"

export TRANSCRIPTS_ROOT
export CURRICULUM_PATH
export OUTPUT_DIR
export PERSIST_TO_DB
export PREPROCESS_MODEL_OVERRIDE

PAYLOAD="$(python - <<'PY'
import json
import os

payload = {
    "transcripts_root": os.environ["TRANSCRIPTS_ROOT"],
    "curriculum_path": os.environ["CURRICULUM_PATH"],
    "output_dir": os.environ["OUTPUT_DIR"],
    "persist_to_db": os.environ.get("PERSIST_TO_DB", "true").lower() == "true",
    "preprocess_model_override": os.environ.get("PREPROCESS_MODEL_OVERRIDE") or None,
}
print(json.dumps(payload, ensure_ascii=False))
PY
)"

curl -sS -X POST "${API_URL}/pipeline/prepare" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}"
