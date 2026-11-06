"""Command-line entry point: ``uv run agent-platform --help``."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .catalog import CatalogError, load_catalog
from .config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-platform")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="validate the agent catalog")
    sub.add_parser("list", help="list agents and teams")
    sub.add_parser("tools", help="print the canvas tool definitions (JSON)")
    s = sub.add_parser("serve", help="start the HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "tools":
        from .canvas.tools import TOOLS

        print(json.dumps(TOOLS, indent=2))
        return 0
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run(
            "agent_platform.api.app:app", host=args.host, port=args.port, reload=args.reload
        )
        return 0

    try:
        catalog = load_catalog(get_settings().catalog_dir)
    except CatalogError as e:
        print(f"catalog invalid:\n{e}", file=sys.stderr)
        return 1
    if args.cmd == "validate":
        print(f"catalog OK: {len(catalog.agents)} agents, {len(catalog.teams)} teams")
    elif args.cmd == "list":
        for a in catalog.agents.values():
            print(f"agent  {a.key:22s} {a.model:20s} skills={a.skills}")
        for t in catalog.teams.values():
            print(f"team   {t.key:22s} {t.coordinator} -> {t.members}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
