# Slides

A slide editor with a chat agent beside it. Ported in part from blattwerk (pgoell's worksheet editor): the block model,
the version check on saves, the plain-word schema errors and the Chromium PDF export.

## The document

A presentation's `doc` is JSON, checked against `backend/app/slides/schema.json`.

- Slide size: 960 x 540 pt (PowerPoint 16:9, 13.333 x 7.5 in). Every length is in pt from the slide's top left.
- `doc = { slides: Slide[], font?: string }`
- `Slide = { id, elements: Element[], background?: "#rrggbb", notes?: string }`. Elements draw in array order: the last lies on top.
- Every element: `id, type, x, y, w, h, rotation?` (degrees clockwise).
- `text`: `paras: Para[]`, `size` (pt), `color`, `font?`, `align: left|center|right`, `valign: top|middle|bottom`, `fill?`, `role?: title|body`.
- `Para = { runs: Run[], list?: bullet|number }`, `Run = { text, bold?, italic?, underline?, color? }`.
- `shape`: `shape: rect|roundRect|ellipse|triangle|line|arrow`, `fill?`, `stroke?`, `strokeWidth?`, and optional text as for `text`.
- `image`: `src` (an `/api/uploads/<name>` path or an https URL), `fit: cover|contain`, `opacity?`.
- `table`: `cells: string[][]` (rows of columns), `header?: boolean`, `size`, `color`, `fill?`, `headerFill?`, `border?`.

## API (all under /api/slides)

- `GET /presentations`, `POST /presentations {title}`, `GET/PATCH/DELETE /presentations/{id}`.
  PATCH `{title?, doc?, version?}`: a doc needs the version it was based on; a stale one answers 409.
- `GET /presentations/{id}/pdf`: Chromium prints `FRONTEND_INTERNAL_URL/print/{id}`.
- `POST /uploads` (multipart `file`), `GET /uploads/{name}`.
- `GET /presentations/{id}/chats`, `POST /presentations/{id}/chats`, `GET /chats/{id}` (messages), `DELETE /chats/{id}`.
- `POST /chats/{id}/messages {text, slide?}` answers an SSE stream: `{type: text, text}`, `{type: tool, name, input}`,
  `{type: tool_result, name, ok, text}`, `{type: doc, version}`, `{type: error, message}`, `{type: done}`.

Data lives in `DATA_DIR` (default `backend/data`): presentations are rows of kind `slides` in the shared store (`basecamp.db`, see `backend/app/store.py`), beside the tables `chats` and `messages`; pictures in `uploads/`. An old `slides.db` moves in on the first start and is renamed `slides.db.migrated`.
