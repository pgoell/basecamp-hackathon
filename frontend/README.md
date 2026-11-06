# Frontend — agent-platform

TypeScript · React · Vite. Renders the **canvas**, the shared state the backend's
agents write to, and lets you pick a team and start a run.

```bash
npm ci
npm run dev           # :5173, proxies /api to http://127.0.0.1:8000 (BACKEND_URL to override)
npm run lint          # eslint
npm run typecheck     # tsc
npm run format:check  # prettier
npm run build         # -> dist/
```

## How the UI stays modular

The frontend has no agent-specific screens. It subscribes to
`GET /api/canvases/{id}/stream` (Server-Sent Events, full snapshot per change)
and renders each block with the component registered for its `type` in
[`src/blocks/registry.ts`](src/blocks/registry.ts). Agents decide _what_ appears
by calling canvas tools on the backend; unknown types fall back to a JSON view.

Add a block type: backend model in `canvas/models.py` → props in
`src/blocks/types.ts` → component + registry entry.

## Docker

The image serves `dist/` with nginx on `:8080` and proxies `/api/` to
`$BACKEND_URL` (default `http://backend:8000`).
