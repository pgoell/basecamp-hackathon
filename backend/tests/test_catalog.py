from pathlib import Path

import pytest

from app.catalog import CATALOG, CatalogError, load_catalog


def test_catalog_loads_and_shares_agents_across_teams():
    catalog = load_catalog(CATALOG)
    assert {"deal-desk", "legal-review"} <= set(catalog.teams)
    assert "legal-reviewer" in catalog.teams["deal-desk"].members
    assert "legal-reviewer" in catalog.teams["legal-review"].members


def test_unknown_agent_reference_is_rejected(tmp_path: Path):
    (tmp_path / "teams").mkdir()
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "teams" / "t.yaml").write_text(
        "name: T\ndescription: d\ncoordinator: nobody\nmembers: [ghost]\nkickoff: go\n"
    )
    with pytest.raises(CatalogError, match="unknown agent"):
        load_catalog(tmp_path)


def test_rfp_team_is_dynamic_with_leads_that_run_their_own_specialists():
    catalog = load_catalog(CATALOG)
    team = catalog.teams["rfp-solutioning"]
    assert team.mode == "dynamic"
    assert team.input.pdf
    cloud = catalog.agents["cloud-architect"]
    assert cloud.is_lead and "finops-analyst" in cloud.members
    assert "cloud-architect" in team.members


def _catalog(tmp_path: Path, agents: dict[str, str], team: str) -> Path:
    for key, extra in agents.items():
        (tmp_path / "agents" / key).mkdir(parents=True)
        (tmp_path / "agents" / key / "agent.yaml").write_text(f"name: {key}\ndescription: d\nmodel: m\n{extra}")
        (tmp_path / "agents" / key / "system.md").write_text("be helpful")
    (tmp_path / "teams").mkdir()
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "teams" / "t.yaml").write_text(f"name: T\ndescription: d\nkickoff: go\n{team}")
    return tmp_path


def test_static_team_cannot_take_a_lead(tmp_path: Path):
    root = _catalog(
        tmp_path, {"boss": "", "lead": "members: [leaf]\n", "leaf": ""}, "coordinator: boss\nmembers: [lead]\n"
    )
    with pytest.raises(CatalogError, match="use mode: dynamic"):
        load_catalog(root)


def test_dynamic_team_takes_a_lead(tmp_path: Path):
    root = _catalog(
        tmp_path,
        {"boss": "", "lead": "members: [leaf]\n", "leaf": ""},
        "coordinator: boss\nmode: dynamic\nmembers: [lead]\n",
    )
    assert load_catalog(root).agents["lead"].is_lead


def test_specialists_cannot_have_members(tmp_path: Path):
    root = _catalog(
        tmp_path,
        {"boss": "", "lead": "members: [mid]\n", "mid": "members: [leaf]\n", "leaf": ""},
        "coordinator: boss\nmode: dynamic\nmembers: [lead]\n",
    )
    with pytest.raises(CatalogError, match="one level only"):
        load_catalog(root)
