#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

API_URL="${STT_QUIZ_API_URL:-http://127.0.0.1:8000}"

curl -sS -X POST "${API_URL}/pipeline/index" \
  -H "Content-Type: application/json" \
  -d '{"corpus_ids": null}'
