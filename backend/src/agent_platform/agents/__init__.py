"""Agent runtime - SCAFFOLD ONLY.

What an agent *is* (name, model, prompt, skills) lives in ``catalog/``.
How a team *runs* is behind the :class:`Orchestrator` interface in
:mod:`.base`. Only :class:`DummyOrchestrator` exists today: it fakes a run so
the frontend and the canvas contract can be built and tested end to end.

TODO(agents team): add a real orchestrator (e.g. Claude Managed Agents with a
coordinator + member roster from the catalog) that attaches
``canvas.tools.TOOLS`` to the coordinator and routes its tool calls through
``canvas.tools.dispatch``. Register it in :func:`get_orchestrator`.
"""

from .base import Orchestrator, RunContext
from .dummy import DummyOrchestrator


def get_orchestrator(name: str = "dummy") -> Orchestrator:
    registry: dict[str, type[Orchestrator]] = {"dummy": DummyOrchestrator}
    try:
        return registry[name]()
    except KeyError:
        raise ValueError(f"unknown orchestrator '{name}', have: {sorted(registry)}") from None


__all__ = ["DummyOrchestrator", "Orchestrator", "RunContext", "get_orchestrator"]
