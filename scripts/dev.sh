#!/usr/bin/env bash
# Run the backend (:8000, auto-reload) and frontend (:3000, hot reload) together.
# Ctrl+C stops both.
#   BACKEND_PORT=8001 FRONTEND_PORT=3001 scripts/dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

[[ -d backend/.venv && -d frontend/node_modules ]] || scripts/setup.sh

if [[ -f backend/.env ]]; then
  set -a; . backend/.env; set +a
fi
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set. Add it to backend/.env." >&2
  exit 1
fi

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in ${pids[@]+"${pids[@]}"}; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd backend && exec uv run fastapi dev app/main.py --port "$BACKEND_PORT") &
pids+=($!)

(cd frontend && PORT="$FRONTEND_PORT" BACKEND_URL="http://localhost:${BACKEND_PORT}" \
  exec bun dev) &
pids+=($!)

echo "backend   http://localhost:${BACKEND_PORT}/docs"
echo "frontend  http://localhost:${FRONTEND_PORT}"

# Stop both as soon as either exits. Polls, because macOS bash 3.2 has no `wait -n`.
while kill -0 "${pids[0]}" 2>/dev/null && kill -0 "${pids[1]}" 2>/dev/null; do
  sleep 1
done
