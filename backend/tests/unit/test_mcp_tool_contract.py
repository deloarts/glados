"""
The committed snapshot of the MCP tool list (mcp-contract/tools.json) matches
what the server offers, so a renamed tool or argument shows up in review.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_mcp_tools.py"


def _export_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_mcp_tools", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mcp_tool_snapshot_is_current() -> None:
    script = _export_script()
    assert script.SNAPSHOT.read_text(encoding="utf-8") == script.render(), (
        "mcp-contract/tools.json is stale; run `poetry run python scripts/export_mcp_tools.py`."
    )


def test_every_tool_has_a_description_and_described_arguments() -> None:
    contract = _export_script().tool_contract()
    for tool in contract["tools"]:
        assert tool["description"].strip(), tool["name"]
        for name, prop in tool["inputSchema"].get("properties", {}).items():
            assert prop.get("description") or "$ref" in prop or "anyOf" in prop, (
                f"{tool['name']}.{name} has no description"
            )
