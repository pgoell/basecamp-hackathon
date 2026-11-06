"""Create or update the environment, skills and agents of every catalog team, and save their ids.

    uv run python -m app.setup

Reads the ids in swarm.json and updates those agents in place, so running it
again after you change backend/catalog/ keeps the same ids. Members are made
first, then each team's coordinator with its members as its roster. Commit
swarm.json: the ids are not secret, and the deployed backend reads them from it.
"""

import json

from anthropic import Anthropic
from anthropic.lib import files_from_dir

from app.catalog import CATALOG, AgentSpec, Catalog, load_catalog
from app.runs import SWARM_FILE

METADATA = {"hackathon": "partner-basecamp-2026"}


def upsert_agent(client: Anthropic, agent_id: str | None, **config) -> str:
    if agent_id:
        current = client.beta.agents.retrieve(agent_id)
        client.beta.agents.update(agent_id, version=current.version, **config)
        print(f"  updated {config['name']:28s} {agent_id}")
        return agent_id
    agent = client.beta.agents.create(**config)
    print(f"  created {config['name']:28s} {agent.id}")
    return agent.id


def main() -> None:
    client = Anthropic()
    catalog = load_catalog(CATALOG)
    swarm = json.loads(SWARM_FILE.read_text()) if SWARM_FILE.exists() else {}
    swarm.setdefault("skills", {})
    swarm.setdefault("agents", {})

    try:
        build(client, swarm, catalog)
    finally:
        # Also after a failure, so a second run reuses what the first made.
        SWARM_FILE.write_text(json.dumps(swarm, indent=2) + "\n")
    print(f"Saved ids to {SWARM_FILE.name}. Commit it.")


def build(client: Anthropic, swarm: dict, catalog: Catalog) -> None:
    if "environment_id" not in swarm:
        env = client.beta.environments.create(
            name="specialist-swarm-env",
            config={"type": "cloud", "networking": {"type": "unrestricted"}},
        )
        swarm["environment_id"] = env.id
        print(f"  created environment {env.id}")

    coordinators = {t.coordinator for t in catalog.teams.values()}
    members = {m for t in catalog.teams.values() for m in t.members} - coordinators
    used = [catalog.agents[k] for k in sorted(members | coordinators)]

    # Skills keep their ids in swarm.json. The org shares one Skills API rate
    # limit and many skills, so look nothing up; titles must be unique in the
    # org, hence the prefix.
    for name in sorted({s for a in used for s in a.skills}):
        skill = catalog.skills[name]
        if skill.source == "custom" and name not in swarm["skills"]:
            made = client.skills.create(display_name=f"Basecamp {name}", files=files_from_dir(str(skill.path)))
            swarm["skills"][name] = made.id
            print(f"  uploaded skill {name} {made.id}")

    def config(agent: AgentSpec, role: str) -> dict:
        skills = [
            {"type": "custom", "skill_id": swarm["skills"][s], "version": "latest"}
            if catalog.skills[s].source == "custom"
            else {"type": "anthropic", "skill_id": s}
            for s in agent.skills
        ]
        web = [{"name": n, "enabled": agent.tools.web} for n in ("web_search", "web_fetch")]
        return {
            "name": agent.name,
            "model": agent.model,
            "system": agent.system,
            "description": agent.description,
            "tools": [{"type": "agent_toolset_20260401", "configs": web}],
            "skills": skills,
            "metadata": {**METADATA, "role": role, "key": agent.key},
        }

    for key in sorted(members):
        swarm["agents"][key] = upsert_agent(client, swarm["agents"].get(key), **config(catalog.agents[key], "member"))
    for team in catalog.teams.values():
        roster = [{"type": "agent", "id": swarm["agents"][m]} for m in team.members]
        swarm["agents"][team.coordinator] = upsert_agent(
            client,
            swarm["agents"].get(team.coordinator),
            **config(catalog.agents[team.coordinator], "coordinator"),
            multiagent={"type": "coordinator", "agents": roster},
        )


if __name__ == "__main__":
    main()
