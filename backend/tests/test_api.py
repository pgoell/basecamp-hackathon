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
    members = client.get("/api/teams/deal-desk").json()["members"]
    assert statuses == ["done"] * len(members)
