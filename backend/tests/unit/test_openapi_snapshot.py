"""
Guards the OpenAPI snapshot policy from inside the normal test run, not just
the dedicated CI step: if either committed snapshot (openapi/pat-v{major}.
{minor}.json or openapi/web-v{major}.{minor}.json) drifts from what the app
actually serves for that surface, this test fails locally too. See
scripts/export_openapi.py and scripts/check_openapi.py for the full policy
and how the snapshots are (re)written.
"""

import json

import pytest

from scripts.export_openapi import SURFACES
from scripts.export_openapi import _iter_refs
from scripts.export_openapi import _security_scheme_names
from scripts.export_openapi import check_snapshot
from scripts.export_openapi import snapshot_path


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_openapi_snapshot_matches_live_schema(surface: str) -> None:
    ok, message = check_snapshot(surface, SURFACES[surface])
    assert ok, message


def test_pat_snapshot_components_are_fully_reachable_and_resolved() -> None:
    """The committed pat snapshot is pruned to just the components its own
    paths need (see _prune_components() in export_openapi.py): every $ref
    it contains must resolve inside its own components, and every
    component present must be reachable from its paths. There must be no
    dangling refs and no unreachable leftovers from the app's full,
    unfiltered component set."""
    doc = json.loads(snapshot_path("pat").read_text())
    components: dict[str, dict[str, object]] = doc.get("components", {})

    for section, name in _iter_refs(doc):
        assert name in components.get(section, {}), f"unresolved $ref #/components/{section}/{name}"

    reachable: set[tuple[str, str]] = set()
    queue: list[tuple[str, str]] = list(_iter_refs(doc.get("paths", {})))
    queue.extend(("securitySchemes", name) for name in _security_scheme_names(doc))
    while queue:
        item = queue.pop()
        section, name = item
        if item in reachable or name not in components.get(section, {}):
            continue
        reachable.add(item)
        queue.extend(_iter_refs(components[section][name]))

    present = {(section, name) for section, names in components.items() for name in names}
    unreachable = present - reachable
    assert not unreachable, f"unreachable components in pat snapshot: {sorted(unreachable)}"
