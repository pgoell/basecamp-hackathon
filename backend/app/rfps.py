"""RFP uploads: a PDF saved under DATA_DIR/rfps with its text pulled out.

Upload makes no model call, so it works with the dummy orchestrator too. A
managed run sends the PDF itself to the Files API when it starts (see
app.runs.upload_rfp) and attaches it to every session it opens.
"""

import io
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from . import store

router = APIRouter(prefix="/api")
MAX_BYTES = 32 * 1024 * 1024  # the Files API and session request limit
PREVIEW_CHARS = 600


@dataclass
class Rfp:
    id: str
    filename: str
    pages: int
    text: str

    @property
    def path(self) -> Path:
        return folder() / f"{self.id}.pdf"


def folder() -> Path:
    # store.DATA is read on each call so tests can point it at a tmp dir.
    path = store.DATA / "rfps"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract(data: bytes) -> tuple[int, str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError) as e:
        raise HTTPException(422, f"Could not read the PDF: {e}") from e
    return len(pages), "\n\n".join(p.strip() for p in pages if p.strip())


def save(filename: str, data: bytes) -> Rfp:
    pages, text = extract(data)
    rfp = Rfp(id=uuid.uuid4().hex, filename=Path(filename).name or "rfp.pdf", pages=pages, text=text)
    rfp.path.write_bytes(data)
    meta = {"filename": rfp.filename, "pages": pages}
    (folder() / f"{rfp.id}.json").write_text(json.dumps(meta))
    (folder() / f"{rfp.id}.txt").write_text(text)
    return rfp


def load(rfp_id: str) -> Rfp:
    # The id is ours: 32 hex characters, never a path.
    if len(rfp_id) != 32 or any(c not in "0123456789abcdef" for c in rfp_id):
        raise HTTPException(404, "unknown RFP")
    meta_file = folder() / f"{rfp_id}.json"
    if not meta_file.is_file():
        raise HTTPException(404, "unknown RFP")
    meta = json.loads(meta_file.read_text())
    text = (folder() / f"{rfp_id}.txt").read_text()
    return Rfp(id=rfp_id, filename=meta["filename"], pages=meta["pages"], text=text)


def summary(rfp: Rfp) -> dict:
    return {
        "id": rfp.id,
        "filename": rfp.filename,
        "pages": rfp.pages,
        "chars": len(rfp.text),
        "preview": rfp.text[:PREVIEW_CHARS],
    }


@router.post("/rfps", status_code=201)
async def upload(file: UploadFile) -> dict:
    name = file.filename or "rfp.pdf"
    if file.content_type != "application/pdf" and not name.lower().endswith(".pdf"):
        raise HTTPException(415, "PDF files only.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "An RFP can be at most 32 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "That file is not a PDF.")
    return summary(save(name, data))


@router.get("/rfps/{rfp_id}")
def get(rfp_id: str) -> dict:
    return summary(load(rfp_id))
