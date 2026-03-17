#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

API_URL="${STT_QUIZ_API_URL:-http://127.0.0.1:8000}"
MODE="${STT_QUIZ_GENERATE_MODE:-rag}"
NUM_QUESTIONS="${STT_QUIZ_NUM_QUESTIONS:-5}"

curl -sS -X POST "${API_URL}/pipeline/generate" \
  -H "Content-Type: application/json" \
  -d "{\"corpus_ids\": null, \"mode\":\"${MODE}\", \"num_questions\": ${NUM_QUESTIONS}, \"choice_count\": null}"
