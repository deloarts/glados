"""GDPR guard of the infoscreen feed. A wall display hangs where anyone can
read it, so no model the feed reaches may carry a person: no name, username,
email, creator, operator, orderer or anything ending in a `_by` reference,
and no reference to a user schema. The guard walks the published OpenAPI
schema, so a field added anywhere under the feed fails it."""

from typing import Any

from src.bootstrap.main import app

_REF_PREFIX = "#/components/schemas/"
_FORBIDDEN_NAMES = frozenset({"full_name", "username", "email"})
_FORBIDDEN_FRAGMENTS = ("operator", "orderer", "creator", "_by")


def _walk(
    node: Any, schemas: dict[str, Any], seen: set[str], problems: list[str], where: str
) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(_REF_PREFIX):
            name = ref.removeprefix(_REF_PREFIX)
            if "user" in name.lower():
                problems.append(f"{where} references {name}")
            if name not in seen:
                seen.add(name)
                _walk(schemas[name], schemas, seen, problems, name)
        for prop in node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}:
            lowered = prop.lower()
            if lowered in _FORBIDDEN_NAMES or any(f in lowered for f in _FORBIDDEN_FRAGMENTS):
                problems.append(f"{where}.{prop}")
        for value in node.values():
            _walk(value, schemas, seen, problems, where)
    elif isinstance(node, list):
        for value in node:
            _walk(value, schemas, seen, problems, where)


def _feed_problems(spec: dict[str, Any]) -> tuple[set[str], list[str]]:
    schemas = spec["components"]["schemas"]
    seen = {"InfoscreenFeedResponse"}
    problems: list[str] = []
    _walk(schemas["InfoscreenFeedResponse"], schemas, seen, problems, "InfoscreenFeedResponse")
    return seen, problems


def test_infoscreen_feed_schema_carries_no_person() -> None:
    seen, problems = _feed_problems(app.openapi())
    # The walk must reach the nested feed models, or it would prove nothing.
    assert {"MachineBoardMachine", "InfoscreenLotRow", "InfoscreenQaRow"} <= seen
    assert problems == []


def test_infoscreen_feed_routes_answer_the_guarded_schema() -> None:
    spec = app.openapi()
    for path in (
        "/api/v1/web/terminal-device/feed",
        "/api/v1/web/infoscreens/{infoscreen_id}/feed",
    ):
        schema = spec["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]
        assert schema["schema"] == {"$ref": f"{_REF_PREFIX}InfoscreenFeedResponse"}


def test_infoscreen_feed_guard_catches_a_person_field() -> None:
    """The guard itself fails on the shapes it exists for."""
    spec = {
        "components": {
            "schemas": {
                "InfoscreenFeedResponse": {
                    "properties": {"rows": {"items": {"$ref": f"{_REF_PREFIX}Row"}}}
                },
                "Row": {
                    "properties": {
                        "started_by": {"type": "string"},
                        "owner": {"$ref": f"{_REF_PREFIX}PublicUserResponse"},
                    }
                },
                "PublicUserResponse": {"properties": {"full_name": {"type": "string"}}},
            }
        }
    }
    _, problems = _feed_problems(spec)
    assert "Row.started_by" in problems
    assert "Row references PublicUserResponse" in problems
    assert "PublicUserResponse.full_name" in problems


def test_terminal_device_state_schema_carries_no_person() -> None:
    """The device state carries the message to terminals a display shows;
    neither may name its author or any other person."""
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    for root in ("TerminalDeviceStateResponse", "TerminalSessionResponse"):
        seen = {root}
        problems: list[str] = []
        _walk(schemas[root], schemas, seen, problems, root)
        assert "TerminalBroadcastMessage" in seen, root
        assert problems == [], root
