"""Offline tests for the rfp_orchestrator engine (no API calls)."""

from __future__ import annotations

import asyncio

import pytest

from rfp_orchestrator import AgentSpec, Limits, run_team

from .fakes import FakeClient

MEMBERS = ["m1", "m2", "m3", "m4", "m5"]
HELPERS = ["h1", "h2", "h3"]


def _spec(key, delegates=(), final=False):
    return AgentSpec(
        key=key,
        name=key.upper(),
        description=f"agent {key}",
        model="fake-model",
        system=f"You are {key}.",
        can_delegate_to=tuple(delegates),
        can_write_final=final,
    )


def roster():
    r = {"lead": _spec("lead", MEMBERS, final=True)}
    r |= {m: _spec(m, HELPERS) for m in MEMBERS}
    r |= {h: _spec(h) for h in HELPERS}
    return r


def _run(tmp_path, limits=None, sinks=None, client=None):
    return asyncio.run(
        run_team(
            roster=roster(),
            root_key="lead",
            task="Answer the RFP in inputs/rfp.md.",
            inputs={"rfp.md": "An RFP."},
            workspace_root=tmp_path / "run",
            limits=limits or Limits(),
            sinks=sinks,
            client=client or FakeClient(),
        )
    )


def test_hierarchy_limits(tmp_path):
    client, events = FakeClient(), []

    async def sink(e):
        events.append(e)

    result = _run(tmp_path, sinks=[sink], client=client)
    assert result.ok
    by_depth = {}
    for a in result.agents:
        by_depth.setdefault(a["depth"], []).append(a)
    assert len(by_depth[0]) == 1
    assert len(by_depth[1]) == 5  # coordinator: unlimited
    assert all(len(a["children"]) == 3 for a in by_depth[1])  # 5 requested, capped at 3
    assert len(by_depth[2]) == 15 and 3 not in by_depth

    # helpers never get a delegate tool
    for call in client.calls:
        if call["system"].startswith("You are h"):
            assert "delegate" not in {t["name"] for t in call["tools"]}

    rejected = [e for e in events if e.type == "delegation_rejected"]
    assert len(rejected) == 5 * 3  # 2 over the cap + 1 outside the roster, per member
    assert any("not in your roster" in e.data["reason"] for e in rejected)
    assert (tmp_path / "run" / "final" / "proposal-response.docx").exists()
    assert (tmp_path / "run" / "events.jsonl").read_text().count("\n") == len(events)


def test_total_agent_cap(tmp_path):
    result = _run(tmp_path, limits=Limits(max_total_agents=4))
    assert len(result.agents) == 4


def test_roster_is_validated(tmp_path):
    bad = roster() | {"lead": _spec("lead", ["ghost"], final=True)}
    with pytest.raises(ValueError, match="unknown agents"):
        asyncio.run(
            run_team(roster=bad, root_key="lead", task="t", inputs={}, workspace_root=tmp_path, client=FakeClient())
        )
