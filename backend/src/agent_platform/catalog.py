"""Load and validate the editable agent catalog.

Layout (all under ``catalog_dir``)::

    agents/<agent-key>/agent.yaml   model, skills, tools, description
    agents/<agent-key>/system.md    the agent's system prompt
    skills/<skill-key>/SKILL.md     custom skills (uploaded via the Skills API)
    teams/<team-key>.yaml           coordinator + members + kickoff
    knowledge/                      documents teams inline into the kickoff

Agents are defined once and referenced by key from any number of teams, so a
single "legal-reviewer" serves the Deal Desk and the Legal Review team alike.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

# Pre-built skills hosted by Anthropic; referenced by name, never uploaded.
ANTHROPIC_SKILLS = frozenset({"docx", "xlsx", "pptx", "pdf"})


class CatalogError(ValueError):
    """The catalog on disk is invalid."""


def fingerprint(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class ToolSettings(BaseModel):
    web: bool = False  # enable web_search + web_fetch in the agent toolset


class AgentSpec(BaseModel):
    key: str
    name: str
    description: str
    model: str
    system: str
    skills: list[str] = Field(default_factory=list)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    tags: list[str] = Field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.model_dump())


class SkillSpec(BaseModel):
    key: str
    source: Literal["custom", "anthropic"]
    path: Path | None = None
    description: str = ""

    @property
    def display_name(self) -> str:
        return self.key.replace("-", " ").title()

    @property
    def fingerprint(self) -> str:
        if self.path is None:
            return self.key
        files = sorted(p for p in self.path.rglob("*") if p.is_file())
        return fingerprint({str(p.relative_to(self.path)): p.read_text() for p in files})


class TeamInput(BaseModel):
    label: str = "Input"
    sample: str | None = None  # file in knowledge/ shown as the default input


class TeamSpec(BaseModel):
    key: str
    name: str
    description: str
    coordinator: str
    members: list[str]
    workflows: bool = False
    budget_usd: float | None = None
    input: TeamInput = Field(default_factory=TeamInput)
    context: list[str] = Field(default_factory=list)
    kickoff: str


class Catalog(BaseModel):
    root: Path
    agents: dict[str, AgentSpec]
    skills: dict[str, SkillSpec]
    teams: dict[str, TeamSpec]

    @property
    def knowledge_dir(self) -> Path:
        return self.root / "knowledge"

    def read_knowledge(self, name: str) -> str:
        path = (self.knowledge_dir / name).resolve()
        if self.knowledge_dir.resolve() not in path.parents:
            raise CatalogError(f"knowledge file escapes catalog: {name}")
        return path.read_text()

    def team(self, key: str) -> TeamSpec:
        try:
            return self.teams[key]
        except KeyError:
            raise KeyError(f"unknown team: {key}") from None


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise CatalogError(f"{path}: expected a mapping")
    return data


def _frontmatter_description(skill_md: Path) -> str:
    text = skill_md.read_text()
    if not text.startswith("---"):
        raise CatalogError(f"{skill_md}: missing YAML frontmatter")
    meta = yaml.safe_load(text.split("---", 2)[1]) or {}
    if not meta.get("name") or not meta.get("description"):
        raise CatalogError(f"{skill_md}: frontmatter needs 'name' and 'description'")
    return str(meta["description"])


def load_catalog(root: Path) -> Catalog:
    if not root.is_dir():
        raise CatalogError(f"catalog directory not found: {root}")

    skills: dict[str, SkillSpec] = {
        key: SkillSpec(key=key, source="anthropic") for key in ANTHROPIC_SKILLS
    }
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        key = skill_md.parent.name
        skills[key] = SkillSpec(
            key=key,
            source="custom",
            path=skill_md.parent,
            description=_frontmatter_description(skill_md),
        )

    agents: dict[str, AgentSpec] = {}
    for agent_yaml in sorted((root / "agents").glob("*/agent.yaml")):
        key = agent_yaml.parent.name
        system_md = agent_yaml.parent / "system.md"
        if not system_md.exists():
            raise CatalogError(f"agent '{key}': missing system.md")
        try:
            agents[key] = AgentSpec(
                key=key, system=system_md.read_text().strip(), **_read_yaml(agent_yaml)
            )
        except ValidationError as e:
            raise CatalogError(f"agent '{key}': {e}") from e

    teams: dict[str, TeamSpec] = {}
    for team_yaml in sorted((root / "teams").glob("*.yaml")):
        key = team_yaml.stem
        try:
            teams[key] = TeamSpec(key=key, **_read_yaml(team_yaml))
        except ValidationError as e:
            raise CatalogError(f"team '{key}': {e}") from e

    catalog = Catalog(root=root, agents=agents, skills=skills, teams=teams)
    _validate(catalog)
    return catalog


def _validate(catalog: Catalog) -> None:
    errors: list[str] = []
    for agent in catalog.agents.values():
        errors += [
            f"agent '{agent.key}': unknown skill '{s}'"
            for s in agent.skills
            if s not in catalog.skills
        ]
    for team in catalog.teams.values():
        for ref in [team.coordinator, *team.members]:
            if ref not in catalog.agents:
                errors.append(f"team '{team.key}': unknown agent '{ref}'")
        if team.coordinator in team.members:
            errors.append(f"team '{team.key}': coordinator cannot also be a member")
        if len(set(team.members)) != len(team.members):
            errors.append(f"team '{team.key}': duplicate members")
        if not 1 <= len(team.members) <= 20:  # Managed Agents roster limit
            errors.append(f"team '{team.key}': needs 1-20 members")
        for doc in [team.input.sample, *team.context]:
            if doc and not (catalog.knowledge_dir / doc).is_file():
                errors.append(f"team '{team.key}': knowledge file not found '{doc}'")
    if errors:
        raise CatalogError("\n".join(errors))
