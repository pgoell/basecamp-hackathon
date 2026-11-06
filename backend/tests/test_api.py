import time

import pytest
from fastapi.testclient import TestClient

from app import dummy, main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "ORCHESTRATOR", "dummy")
    monkeypatch.setattr(dummy.DummyOrchestrator, "__init__", lambda self: setattr(self, "step", 0))
    with TestClient(main.app) as c:
        yield c


def test_catalog_endpoints(client):
    assert client.get("/api/health").status_code == 200
    assert "deal-desk" in {t["key"] for t in client.get("/api/teams").json()}
    detail = client.get("/api/teams/deal-desk").json()
    assert detail["coordinator_agent"]["key"] == "deal-desk-partner"


def test_tool_endpoint_returns_409_on_stale_version(client):
    c = client.post("/api/canvases", json={"title": "t"}).json()
    block = {"type": "markdown", "props": {"text": "x"}}
    url = f"/api/canvases/{c['id']}/tools/add_block"
    assert client.post(url, json={"version": c["version"], "block": block}).status_code == 200
    stale = client.post(url, json={"version": c["version"], "block": block})
    assert stale.status_code == 409
    assert stale.json()["detail"]["actual"] == c["version"] + 1


def test_dummy_run_fills_canvas(client):
    r = client.post("/api/teams/deal-desk/runs", json={})
    assert r.status_code == 202
    canvas_id = r.json()["canvas_id"]
    for _ in range(100):
        blocks = client.get(f"/api/canvases/{canvas_id}").json()["blocks"]
        if any(b["type"] == "file" for b in blocks):
            break
        time.sleep(0.05)
    types = {b["type"] for b in blocks}
    assert {"callout", "markdown", "status", "table", "kv", "file"} <= types
    statuses = [b["props"]["state"] for b in blocks if b["type"] == "status"]
    assert statuses == ["done"] * 4


def _pdf() -> bytes:
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _wait_for_file(client, canvas_id: int) -> list[dict]:
    for _ in range(200):
        blocks = client.get(f"/api/canvases/{canvas_id}").json()["blocks"]
        if any(b["type"] == "file" for b in blocks):
            return blocks
        time.sleep(0.05)
    raise AssertionError("the run never finished")


def test_upload_rfp_pdf(client):
    r = client.post("/api/rfps", files={"file": ("acme.pdf", _pdf(), "application/pdf")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "acme.pdf" and body["pages"] == 1
    assert client.get(f"/api/rfps/{body['id']}").json()["id"] == body["id"]


def test_upload_rejects_non_pdf(client):
    r = client.post("/api/rfps", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    assert client.get("/api/rfps/../../etc").status_code == 404


def test_team_detail_shows_leads_and_their_specialists(client):
    detail = client.get("/api/teams/rfp-solutioning").json()
    assert detail["mode"] == "dynamic" and detail["input_pdf"]
    assert "finops-analyst" in detail["sub_agents"]


def test_dynamic_dummy_run_builds_an_org_tree(client):
    rfp = client.post("/api/rfps", files={"file": ("acme.pdf", _pdf(), "application/pdf")}).json()
    r = client.post("/api/teams/rfp-solutioning/runs", json={"rfp_id": rfp["id"]})
    assert r.status_code == 202
    # A blank PDF has no text, so the dummy engages only the leads every bid needs.
    blocks = _wait_for_file(client, r.json()["canvas_id"])
    org = next(b for b in blocks if b["type"] == "org")
    nodes = {n["id"]: n for n in org["props"]["nodes"]}
    assert nodes["rfp-orchestrator"]["state"] == "done"
    assert nodes["pricing-specialist"]["state"] == "done"
    assert nodes["cloud-architect"]["state"] == "idle"


def test_dynamic_dummy_run_engages_sub_specialists_from_text(client):
    r = client.post("/api/teams/rfp-solutioning/runs", json={})  # the sample RFP: Azure data platform
    blocks = _wait_for_file(client, r.json()["canvas_id"])
    nodes = {n["id"]: n for n in next(b for b in blocks if b["type"] == "org")["props"]["nodes"]}
    assert nodes["cloud-architect"]["state"] == "done"
    assert nodes["cloud-architect/finops-analyst"]["parent"] == "cloud-architect"
    assert nodes["data-engineer/pipeline-engineer"]["state"] == "done"
