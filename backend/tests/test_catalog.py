from pathlib import Path

import pytest

from agent_platform.catalog import CatalogError, load_catalog

CATALOG = Path(__file__).resolve().parents[1] / "catalog"


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
