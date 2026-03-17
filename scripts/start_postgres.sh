#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

start_docker_desktop() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker command not found" >&2
    exit 1
  fi

  if docker info >/dev/null 2>&1; then
    return 0
  fi

  if docker desktop start --detach >/dev/null 2>&1; then
    for _ in {1..30}; do
      if docker info >/dev/null 2>&1; then
        return 0
      fi
      sleep 2
    done
  fi

  echo "docker daemon unavailable" >&2
  exit 1
}

start_docker_desktop
docker compose up -d postgres >/dev/null
"${ROOT_DIR}/.venv_quizsvc/bin/python" "${ROOT_DIR}/scripts/wait_for_db.py"
