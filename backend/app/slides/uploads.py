"""Pictures for image elements, stored in DATA_DIR/uploads under a random name."""

import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.slides.db import UPLOADS

router = APIRouter(prefix="/api/slides")
TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}
MAX_BYTES = 10 * 1024 * 1024


@router.post("/uploads")
async def upload(file: UploadFile) -> dict:
    ext = TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(415, f"Pictures only: {', '.join(TYPES.values())}.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "A picture can be at most 10 MB.")
    name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOADS / name).write_bytes(data)
    return {"src": f"/api/slides/uploads/{name}"}


@router.get("/uploads/{name}")
def picture(name: str) -> FileResponse:
    path = UPLOADS / name
    # The name is ours: a random hex and an extension, never a path.
    if "/" in name or ".." in name or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
