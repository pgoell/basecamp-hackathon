"""The catalog-driven hierarchy orchestrator, end to end through the API (fake client)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app import hierarchy, main
from app.catalog import CATALOG, load_catalog

from .fakes import FakeClient


def test_roster_from_catalog():
    cat = load_catalog(CATALOG)
    team = cat.team("deal-desk")
    roster = hierarchy.build_roster(cat, team)
    lead = roster[team.coordinator]
    assert lead.can_write_final and set(lead.can_delegate_to) == set(team.members)
    assert all(set(roster[m].can_delegate_to) == set(team.helpers) for m in team.members)
    assert all(roster[h].can_delegate_to == () for h in team.helpers)
    pricing = roster["pricing-specialist"].full_system_prompt(3)
    assert '<skill name="pricing-playbook">' in pricing and "at most 3 tasks" in pricing
    assert "docx" not in {name for name, _ in lead.skills}  # Anthropic skills are not injected


@pytest.fixture
def client(tmp_path, monkeypatch):
    real = hierarchy.hierarchical

    async def fake(ctx):
        return await real(ctx, client=FakeClient())

    monkeypatch.setattr(main, "ORCHESTRATOR", "hierarchy")
    monkeypatch.setattr(hierarchy, "hierarchical", fake)
    monkeypatch.setattr(hierarchy, "RUNS_DIR", tmp_path / "runs")
    with TestClient(main.app) as c:
        yield c


def test_hierarchy_run_fills_canvas(client):
    r = client.post("/api/teams/deal-desk/runs", json={})
    assert r.status_code == 202
    canvas_id = r.json()["canvas_id"]
    for _ in range(200):
        blocks = client.get(f"/api/canvases/{canvas_id}").json()["blocks"]
        if any(b["type"] == "kv" for b in blocks):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("run did not finish")

    statuses = [b for b in blocks if b["type"] == "status"]
    assert len(statuses) == 1 + 5 + 15  # lead, members, 3 helpers each
    assert {b["props"]["state"] for b in statuses} == {"done"}
    assert any("(for Pricing Specialist)" in b["title"] for b in statuses)

    files = [b for b in blocks if b["type"] == "file"]
    assert {f["props"]["filename"] for f in files} == {"proposal-response.md", "proposal-response.docx"}
    url = next(f["props"]["url"] for f in files if f["props"]["filename"].endswith(".md"))
    got = client.get(url)
    assert got.status_code == 200 and "Executive summary" in got.text

    assert client.get(f"/api/runs/{canvas_id}/files/work/notes.md").status_code == 200
    assert client.get(f"/api/runs/{canvas_id}/files/inputs/rfp.md").status_code == 404
    assert client.get(f"/api/runs/{canvas_id}/files/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_leads_delegate_to_their_own_crew():
    cat = load_catalog(CATALOG)
    team = cat.team("rfp-solutioning")
    roster = hierarchy.build_roster(cat, team)
    assert set(roster["cloud-architect"].can_delegate_to) == {
        "network-engineer",
        "cloud-security-engineer",
        "finops-analyst",
    }
    assert set(roster["pricing-specialist"].can_delegate_to) == set(team.helpers)
    assert roster["finops-analyst"].can_delegate_to == ()
    assert not roster["cloud-architect"].can_write_final


def test_rfp_run_builds_org_tree_with_crews(client):
    r = client.post("/api/teams/rfp-solutioning/runs", json={})
    canvas_id = r.json()["canvas_id"]
    for _ in range(300):
        blocks = client.get(f"/api/canvases/{canvas_id}").json()["blocks"]
        if any(b["type"] == "kv" for b in blocks):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("run did not finish")
    nodes = next(b for b in blocks if b["type"] == "org")["props"]["nodes"]
    by_id = {n["id"]: n for n in nodes}
    assert by_id["rfp-orchestrator"]["state"] == "done" and by_id["rfp-orchestrator"]["parent"] is None
    assert by_id["cloud-architect"]["parent"] == "rfp-orchestrator"
    # The fake member delegates to the first agent of its roster: the lead's own crew.
    crew = [n for n in nodes if n["parent"] == "cloud-architect"]
    assert crew and {n["agent"] for n in crew} == {"network-engineer"}
    helpers = [n for n in nodes if n["parent"] == "pricing-specialist"]
    assert {n["agent"] for n in helpers} == {"document-analyst"}
