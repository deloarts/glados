"""
Snapshots the tool list of the MCP surface to mcp-contract/tools.json: every
tool with its input schema, annotations, kind and required permissions,
every prompt with its arguments and every resource template. Agent clients
and prompts rely on these names and arguments, so the snapshot makes a
change to them visible in review, and tests/unit/test_mcp_tool_contract.py
fails while it is stale.

Usage:
    poetry run python scripts/export_mcp_tools.py            # (re)write the snapshot
    poetry run python scripts/export_mcp_tools.py --check     # verify only, exit 1 on drift
"""

import os

# Importing the composition root validates the settings, as in
# scripts/export_openapi.py, so throwaway defaults stand in for a deployment.
if not os.getenv("ENV_FILE"):
    os.environ.setdefault("DEBUG", "false")
    os.environ.setdefault("SECURITY__SECRET_KEY_PERSISTENT", "mcp-export-persistent-key")
    os.environ.setdefault("SECURITY__SECRET_KEY_NON_PERSISTENT", "mcp-export-non-persistent-key")
    os.environ.setdefault("DATABASE__URL", "sqlite:///./.mcp-export.db")
    os.environ.setdefault("REDIS__URL", "redis://localhost:6379/15")
    os.environ.setdefault("INIT__FULL_NAME", "MCP Export")
    os.environ.setdefault("INIT__MAIL", "mcp-export@example.com")
    os.environ.setdefault("INIT__PASSWORD", "mcp-export-password")

# isort: split

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.bootstrap.agents import AGENT_CATALOGS
from src.modules.platform.adapters.inbound.mcp.server import AgentServer
from src.modules.platform.const import VERSION

SNAPSHOT = Path(__file__).resolve().parents[1] / "mcp-contract" / "tools.json"


def tool_contract() -> dict[str, Any]:
    """The tool list as agents see it, in a stable order."""
    server = AgentServer(AGENT_CATALOGS, version=VERSION)
    return {
        "tools": [
            {
                **AgentServer.describe(tool).model_dump(
                    mode="json", by_alias=True, exclude_none=True
                ),
                "x-glados-kind": tool.kind.value,
                "x-glados-requires": list(tool.requires),
            }
            for tool in sorted(server.tools.values(), key=lambda t: t.name)
        ],
        "prompts": [
            {
                "name": prompt.name,
                "title": prompt.title,
                "description": prompt.description,
                "arguments": [
                    {"name": a.name, "description": a.description, "required": a.required}
                    for a in prompt.arguments
                ],
            }
            for prompt in sorted(server.prompts.values(), key=lambda p: p.name)
        ],
        "resources": [
            {
                "uriTemplate": r.uri_template,
                "name": r.name,
                "title": r.title,
                "description": r.description,
                "tool": r.tool,
                "argument": r.argument,
            }
            for r in sorted(server.resources, key=lambda r: r.uri_template)
        ],
    }


def render() -> str:
    return json.dumps(tool_contract(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when the snapshot is stale")
    args = parser.parse_args()
    current = render()
    if args.check:
        if not SNAPSHOT.exists() or SNAPSHOT.read_text(encoding="utf-8") != current:
            print(f"{SNAPSHOT.name} is stale; run scripts/export_mcp_tools.py.")
            return 1
        print(f"{SNAPSHOT.name} matches the tool list (OK).")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(current, encoding="utf-8")
    print(
        f"Wrote {SNAPSHOT.relative_to(Path.cwd()) if SNAPSHOT.is_relative_to(Path.cwd()) else SNAPSHOT}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
