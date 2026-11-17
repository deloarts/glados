"""
Structural tests for the generated PDM Web API operation catalogue: the
count and mutating split match the documented 113/28, every operation id is
unique, every `{name}` path placeholder has a matching "path" param spec and
every `?a={a}` query placeholder has a matching "query" param spec, and
find_operation round-trips. These check the generator's output stayed a
faithful mirror of operations.json, not any operation's business meaning.
"""

import re

from src.modules.external_data.adapters.outbound.external.pdm.catalogue import OPERATIONS
from src.modules.external_data.adapters.outbound.external.pdm.catalogue import find_operation

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def test_catalogue_has_113_operations() -> None:
    assert len(OPERATIONS) == 113


def test_catalogue_has_28_mutating_operations() -> None:
    assert sum(1 for op in OPERATIONS if op.mutating) == 28


def test_operation_ids_are_unique() -> None:
    ids = [op.id for op in OPERATIONS]
    assert len(ids) == len(set(ids))


def test_every_path_placeholder_has_a_path_param_spec() -> None:
    for op in OPERATIONS:
        base_path, _, _query_template = op.path.partition("?")
        by_name = {p.name: p for p in op.params}
        for name in _PLACEHOLDER_RE.findall(base_path):
            assert name in by_name, f"{op.id}: {{{name}}} in path has no param spec"
            assert by_name[name].location == "path", f"{op.id}: {name} should be a path param"


def test_every_query_placeholder_has_a_query_param_spec() -> None:
    for op in OPERATIONS:
        _base_path, _, query_template = op.path.partition("?")
        by_name = {p.name: p for p in op.params}
        for name in _PLACEHOLDER_RE.findall(query_template):
            assert name in by_name, f"{op.id}: {{{name}}} in query template has no param spec"
            assert by_name[name].location == "query", f"{op.id}: {name} should be a query param"


def test_find_operation_round_trips_every_id() -> None:
    for op in OPERATIONS:
        assert find_operation(op.id) is op


def test_find_operation_returns_none_for_unknown_id() -> None:
    assert find_operation("does-not-exist") is None


def test_authenticate_operation_matches_the_documented_contract() -> None:
    spec = find_operation("post_api_vaultname_authenticate")
    assert spec is not None
    assert spec.method == "POST"
    assert spec.path == "api/{vaultName}/authenticate"
    assert spec.has_body is True
    assert spec.mutating is False
    param_names = {p.name for p in spec.params}
    assert {"vaultName", "Username", "Password"} <= param_names
