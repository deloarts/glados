"""
Guards that every object schema reached only from responses lists all of its
properties as required. A response always carries each field, defaulted ones
included, and the frontend generates its types from these schemas, so a
response schema that left a defaulted field optional would force an override
on the frontend. Response schemas get this from `ResponseModel` or, for a DTO
returned directly, `ResultModel`. Schemas a request also reaches keep their
defaulted fields optional and are not checked.
"""

from typing import Any

import pytest

from src.bootstrap.main import app

# The error bodies, whose optional fields are genuine: FastAPI's own
# validation errors, and ErrorResponse, whose `code` a refusal of the HTTP
# layer itself, such as a missing token or a rate limit, does not carry.
_ERROR_SCHEMAS = frozenset({"HTTPValidationError", "ValidationError", "ErrorResponse"})
_REF_PREFIX = "#/components/schemas/"


def _refs(node: Any, out: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(_REF_PREFIX):
            out.add(ref.removeprefix(_REF_PREFIX))
        for value in node.values():
            _refs(value, out)
    elif isinstance(node, list):
        for value in node:
            _refs(value, out)


def _closure(seeds: set[str], schemas: dict[str, Any]) -> set[str]:
    seen: set[str] = set()
    stack = list(seeds)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        found: set[str] = set()
        _refs(schemas.get(name, {}), found)
        stack.extend(found - seen)
    return seen


@pytest.fixture
def spec() -> dict[str, Any]:
    return app.openapi()


def test_response_only_schemas_require_every_property(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    request_seeds: set[str] = set()
    response_seeds: set[str] = set()
    for item in spec["paths"].values():
        for operation in item.values():
            if not isinstance(operation, dict):
                continue
            _refs(operation.get("requestBody", {}), request_seeds)
            _refs(operation.get("parameters", []), request_seeds)
            _refs(operation.get("responses", {}), response_seeds)
    response_only = _closure(response_seeds, schemas) - _closure(request_seeds, schemas)

    optional = {
        name: sorted(set(schema["properties"]) - set(schema.get("required", [])))
        for name, schema in schemas.items()
        if name in response_only and name not in _ERROR_SCHEMAS and "properties" in schema
    }
    assert {name: fields for name, fields in optional.items() if fields} == {}
