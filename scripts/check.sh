#!/usr/bin/env bash
# Run the same checks as .github/workflows/check.yml, locally.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> backend imports"
(cd backend && uv sync --frozen && ANTHROPIC_API_KEY=x uv run python -c "import app.main")

echo "==> frontend builds"
(cd frontend && bun install --frozen-lockfile && bunx tsc && bun run build)

echo "All checks passed."
