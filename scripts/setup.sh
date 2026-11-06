#!/usr/bin/env bash
# One-time setup: install backend (uv) and frontend (Bun) dependencies and
# create backend/.env if it is missing.
set -euo pipefail
cd "$(dirname "$0")/.."

need() { command -v "$1" >/dev/null || { echo "missing: $1, install it from $2" >&2; exit 1; }; }
need uv  "https://docs.astral.sh/uv/getting-started/installation/"
need bun "https://bun.sh"

echo "==> backend: uv sync"
(cd backend && uv sync)

echo "==> frontend: bun install"
(cd frontend && bun install)

if [[ ! -f backend/.env ]]; then
  echo "ANTHROPIC_API_KEY=" > backend/.env
  echo "Created backend/.env (gitignored). Put your key in it before running scripts/dev.sh."
fi

echo "Done. Start both with: scripts/dev.sh"
