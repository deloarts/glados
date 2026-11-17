"""
The backend tags every route by client: web, pat, key, and public (the
pre-login branding routes). src/modules/platform/adapters/inbound/api/docs.py serves a schema
for web, pat and key. This script snapshots two groupings to disk as
committed contracts:

  * openapi/pat-v{major}.{minor}.json: the pat, key and public routes,
    combined into one document. This is the frozen external contract used
    by outside integrations (e.g. the SW add-in); once a major.minor has a
    release tag, scripts/check_openapi.py refuses further changes to it.
    `_filtered_openapi()` only filters `paths`; `components` is always the
    app's full, unfiltered set. Left as-is, any web-only schema change
    would touch this file too and trip the freeze, defeating the point of
    the split. So the pat document is additionally pruned to only the
    `components` (and, if present, top-level `tags`) transitively
    reachable from its own paths (see `_prune_components()`).
  * openapi/web-v{major}.{minor}.json: the web surface only, the one the
    frontend's own client talks to. It may change on any commit; the
    frontend regenerates its types from it (frontend/scripts/
    generate-api-types.ts) and is free to track it closely rather than
    waiting for a release. Not pruned: it must stay equivalent to what
    /api/v1/web/openapi.json serves live.

Usage:
    poetry run python scripts/export_openapi.py            # (re)write both snapshots
    poetry run python scripts/export_openapi.py --check     # verify only, exit 1 on drift
"""

import os

# `cfg` (src/modules/platform/infrastructure/config/settings.py) validates security/database/
# redis/init settings at import time, so importing `src.bootstrap.main` requires them
# to already be in the environment. tests/conftest.py solves this the same
# way for pytest: if no real ENV_FILE is configured, fall back to throwaway
# defaults so the app is importable without a real deployment around it.
if not os.getenv("ENV_FILE"):
    os.environ.setdefault("DEBUG", "false")
    os.environ.setdefault("SECURITY__SECRET_KEY_PERSISTENT", "openapi-export-persistent-key")
    os.environ.setdefault(
        "SECURITY__SECRET_KEY_NON_PERSISTENT", "openapi-export-non-persistent-key"
    )
    os.environ.setdefault("DATABASE__URL", "sqlite:///./.openapi-export.db")
    os.environ.setdefault("REDIS__URL", "redis://localhost:6379/15")
    os.environ.setdefault("INIT__FULL_NAME", "OpenAPI Export")
    os.environ.setdefault("INIT__MAIL", "openapi-export@example.com")
    os.environ.setdefault("INIT__PASSWORD", "openapi-export-password")

# isort: split

import argparse
import difflib
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.docs import _filtered_openapi
from src.modules.platform.const import VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_DIR = REPO_ROOT / "openapi"
DIFF_LINE_LIMIT = 200

# Surface -> tag prefixes it bundles. "pat" is the combined, frozen external
# contract (pat + key + public); "web" is the frontend-only surface.
SURFACES: dict[str, tuple[str, ...]] = {
    "pat": ("pat/", "key/", "public/"),
    "web": ("web/",),
}

# Only the pat snapshot is pruned to its reachable components; the web
# snapshot must stay exactly what /api/v1/web/openapi.json serves.
_PRUNED_SURFACES = frozenset({"pat"})

_COMPONENT_REF_RE = re.compile(r"^#/components/([^/]+)/(.+)$")


def current_minor() -> str:
    """The `major.minor` component of src.modules.platform.const.VERSION, e.g. "0.1" for "0.1.0"."""
    parts = VERSION.split(".")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse major.minor from VERSION={VERSION!r}")
    return f"{int(parts[0])}.{int(parts[1])}"


def snapshot_path(surface: str) -> Path:
    """Path to the committed snapshot for `surface` at the current minor version."""
    return OPENAPI_DIR / f"{surface}-v{current_minor()}.json"


def _merged_openapi(tag_prefixes: tuple[str, ...]) -> dict[str, Any]:
    """Union of docs.py's existing `_filtered_openapi(app, prefix)` over
    each prefix, reused unchanged (it only ever takes one prefix at a time).
    `paths` is a plain union, since the surfaces are disjoint and each route
    is tagged for exactly one. Everything else in the document (openapi
    version, info, components, ...) is identical across every surface's
    filtered schema since only `paths` is filtered, so the first surface's
    copy is used as the base."""
    merged_paths: dict[str, Any] = {}
    base: dict[str, Any] | None = None
    for prefix in tag_prefixes:
        filtered = _filtered_openapi(app, prefix)
        if base is None:
            base = filtered
        merged_paths.update(filtered["paths"])
    assert base is not None, "tag_prefixes must be non-empty"
    return {**base, "paths": merged_paths}


def _iter_refs(node: Any) -> Iterator[tuple[str, str]]:
    """Yield (section, name) for every '#/components/<section>/<name>'
    `$ref` found anywhere under `node` (walks dicts/lists recursively)."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            m = _COMPONENT_REF_RE.match(ref)
            if m:
                yield m.group(1), m.group(2)
        for value in node.values():
            yield from _iter_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_refs(item)


def _security_scheme_names(schema: dict[str, Any]) -> Iterator[str]:
    """Security scheme names referenced by name (not by `$ref`) from a
    top-level `security` and from each kept operation's own `security`."""
    security_lists = [schema.get("security", [])]
    security_lists.extend(
        operation["security"]
        for operations in schema.get("paths", {}).values()
        for operation in operations.values()
        if "security" in operation
    )
    for security in security_lists:
        for requirement in security or []:
            yield from requirement


def _prune_components(schema: dict[str, Any]) -> dict[str, Any]:
    """Prune `components` (and top-level `tags`, if present) down to what
    is transitively reachable from `schema["paths"]`: walk the paths for
    `$ref`s, then keep following `$ref`s inside whatever that reaches until
    a fixpoint. `securitySchemes` are kept when referenced by name from a
    kept operation's `security` or a top-level `security`. Sections that
    end up empty are dropped entirely."""
    components: dict[str, dict[str, Any]] = schema.get("components", {})
    kept: dict[str, set[str]] = {section: set() for section in components}

    queue: list[tuple[str, str]] = list(_iter_refs(schema.get("paths", {})))
    queue.extend(("securitySchemes", name) for name in _security_scheme_names(schema))

    while queue:
        section, name = queue.pop()
        if section not in kept or name in kept[section]:
            continue
        definition = components.get(section, {}).get(name)
        if definition is None:
            continue  # dangling/unresolvable ref; nothing to keep or recurse into
        kept[section].add(name)
        queue.extend(_iter_refs(definition))

    pruned_components = {
        section: {name: components[section][name] for name in sorted(names)}
        for section, names in kept.items()
        if names
    }
    pruned = {**schema, "components": pruned_components}

    if "tags" in schema:
        used_tag_names = {
            tag
            for operations in schema.get("paths", {}).values()
            for operation in operations.values()
            for tag in operation.get("tags", [])
        }
        pruned["tags"] = [tag for tag in schema["tags"] if tag.get("name") in used_tag_names]

    return pruned


def _build_surface_schema(surface: str, tag_prefixes: tuple[str, ...]) -> dict[str, Any]:
    """The live OpenAPI document for one snapshot surface, shared by
    write_snapshot() and check_snapshot()/--check so "committed == live"
    always compares the same document: `_merged_openapi` filtered to the
    given tag prefixes, then (pat only) pruned to its reachable components."""
    schema = _merged_openapi(tag_prefixes)
    if surface in _PRUNED_SURFACES:
        schema = _prune_components(schema)
    return schema


def serialize_schema(surface: str, tag_prefixes: tuple[str, ...]) -> str:
    """The live schema for `surface`, serialised deterministically so the
    committed file diffs cleanly and byte-for-byte equality is meaningful."""
    schema = _build_surface_schema(surface, tag_prefixes)
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _render_diff(existing: str, new: str, label: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
        )
    )
    if not diff_lines:
        return ""
    truncated = diff_lines[:DIFF_LINE_LIMIT]
    rendered = "".join(truncated)
    if len(diff_lines) > DIFF_LINE_LIMIT:
        rendered += (
            f"\n... diff truncated ({len(diff_lines)} lines total, "
            f"showing first {DIFF_LINE_LIMIT}) ...\n"
        )
    return rendered


def check_snapshot(surface: str, tag_prefixes: tuple[str, ...]) -> tuple[bool, str]:
    """Verify the committed snapshot for `surface` at the current minor
    matches the live, filtered schema. Returns (ok, message); message
    includes a capped unified diff on mismatch."""
    target = snapshot_path(surface)
    label = target.relative_to(REPO_ROOT).as_posix()
    new_content = serialize_schema(surface, tag_prefixes)

    if not target.exists():
        return False, f"{label} does not exist yet."

    existing_content = target.read_text()
    if existing_content == new_content:
        return True, f"{label} matches the live schema (OK)."

    diff = _render_diff(existing_content, new_content, label)
    return False, f"{label} differs from the live schema:\n{diff}"


def write_snapshot() -> None:
    """(Re)write both surface snapshots for the current minor and remove any
    other file under openapi/, such as a stale minor's snapshot, so only the
    current minor's two files are ever committed."""
    OPENAPI_DIR.mkdir(parents=True, exist_ok=True)
    targets = {surface: snapshot_path(surface) for surface in SURFACES}

    removed = []
    for existing_file in sorted(OPENAPI_DIR.glob("*.json")):
        if existing_file not in targets.values():
            existing_file.unlink()
            removed.append(existing_file.name)

    for surface, tag_prefixes in SURFACES.items():
        target = targets[surface]
        content = serialize_schema(surface, tag_prefixes)
        target.write_text(content)
        print(f"Wrote {target.relative_to(REPO_ROOT).as_posix()} ({len(content)} bytes).")

    if removed:
        print(f"Removed stale snapshot(s): {', '.join(removed)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify both committed snapshots match the live schema; do not write",
    )
    args = parser.parse_args(argv)

    if args.check:
        ok = True
        for surface, tag_prefixes in SURFACES.items():
            surface_ok, message = check_snapshot(surface, tag_prefixes)
            print(message)
            ok = ok and surface_ok
        return 0 if ok else 1

    write_snapshot()
    return 0


if __name__ == "__main__":
    sys.exit(main())
