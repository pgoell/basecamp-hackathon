"""Limits of the agent tree and API settings.

All limits live here so they are easy to tune (and to set via env vars on the
server).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Models that accept the server-side `fallbacks: "default"` parameter on the
# Claude API (on a refusal the request is retried on a recommended model).
FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-opus-5"})
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _int_env(name: str, default: int | None) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return None if raw.lower() == "none" else int(raw)


@dataclass(frozen=True)
class Limits:
    """Shape of the agent tree.

    depth 0 = coordinator, depth 1 = specialists, depth 2 = helpers.
    """

    # Deepest level that may exist. Agents at this depth get no delegate tool.
    max_depth: int = 2
    # Max children per agent, indexed by the parent's depth. None = unlimited.
    # Coordinator: unlimited; specialists: up to 3 helpers each.
    max_children_by_depth: dict[int, int | None] = field(default_factory=lambda: {0: None, 1: 3})
    # Safety nets for the whole run (cost / rate-limit protection).
    max_total_agents: int = 40
    max_concurrent_requests: int = 8
    # Max model turns per agent loop before it is stopped.
    max_turns_per_agent: int = 30
    max_tokens: int = 64000

    def max_children(self, depth: int) -> int | None:
        if depth >= self.max_depth:
            return 0
        return self.max_children_by_depth.get(depth)

    @classmethod
    def from_env(cls) -> Limits:
        return cls(
            max_depth=_int_env("RFP_MAX_DEPTH", 2) or 2,
            max_children_by_depth={
                0: _int_env("RFP_MAX_CHILDREN_COORDINATOR", None),
                1: _int_env("RFP_MAX_CHILDREN_SPECIALIST", 3),
            },
            max_total_agents=_int_env("RFP_MAX_TOTAL_AGENTS", 40) or 40,
            max_concurrent_requests=_int_env("RFP_MAX_CONCURRENT_REQUESTS", 8) or 8,
        )
