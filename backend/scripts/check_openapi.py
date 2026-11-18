"""
CI entry point for the OpenAPI snapshot policy.

Step A checks that both committed snapshots, openapi/pat-v{major}.{minor}.json
and openapi/web-v{major}.{minor}.json, equal what the live app currently
serves for their respective surfaces (see scripts/export_openapi.py).

Step B applies only to the pat snapshot (pat + key + public: the frozen
external contract). Once any v{major}.{minor}.* release tag exists, the pat
snapshot must not have changed since the lowest (first) such tag. An API
change after release means the minor must be bumped instead. The web
snapshot is exempt: it belongs to the frontend only and may change on any
commit.

Step B fails closed under `--strict`, which CI passes and which a `CI` or
`GITHUB_ACTIONS` environment variable turns on as well: a failed
`git fetch --tags` or a snapshot missing at the released tag fails the check,
since either would otherwise let a changed contract through unseen. Run
locally without it, both only warn, so the check still works offline.

Usage:
    poetry run python scripts/check_openapi.py [--strict]
"""

import argparse
import os
import re
import subprocess
import sys

from scripts.export_openapi import REPO_ROOT
from scripts.export_openapi import SURFACES
from scripts.export_openapi import check_snapshot
from scripts.export_openapi import current_minor
from scripts.export_openapi import snapshot_path

# The frozen external contract: only this surface is subject to Step B.
_FROZEN_SURFACE = "pat"

# Matches a release tag exactly, e.g. "v0.1.3", deliberately excludes
# pre-releases like "v0.1.3-rc1", which must not freeze the snapshot.
_RELEASE_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _step_a() -> bool:
    ok = True
    for surface, tag_prefixes in SURFACES.items():
        surface_ok, message = check_snapshot(surface, tag_prefixes)
        label = snapshot_path(surface).relative_to(REPO_ROOT).as_posix()
        if not surface_ok:
            print(f"{label} is out of date, run `poetry run python scripts/export_openapi.py`")
            print(message)
        else:
            print(message)
        ok = ok and surface_ok
    return ok


def _matching_release_tags(minor: str) -> list[str]:
    """Release tags (no -rc suffix) for this exact major.minor, sorted by
    patch number ascending (sort -V semantics, done with an int key)."""
    result = subprocess.run(
        ["git", "tag", "--list", f"v{minor}.*"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    matches: list[tuple[int, str]] = []
    for tag in candidates:
        m = _RELEASE_TAG_RE.match(tag)
        if m and f"{int(m.group(1))}.{int(m.group(2))}" == minor:
            matches.append((int(m.group(3)), tag))
    matches.sort(key=lambda pair: pair[0])
    return [tag for _, tag in matches]


def strict_by_default() -> bool:
    """True on a CI runner, which sets `CI` (and GitHub Actions also
    `GITHUB_ACTIONS`) to "true"."""
    return any(
        os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}
        for name in ("CI", "GITHUB_ACTIONS")
    )


def _next_minor(minor: str) -> str:
    major, minor_number = minor.split(".")
    return f"{major}.{int(minor_number) + 1}.0"


def _unverifiable(reason: str, *, strict: bool) -> bool:
    """A freeze check that could not run fails under `strict` and only warns
    otherwise."""
    if strict:
        print(f"Error: {reason}; the freeze check cannot run, so the snapshot check fails.")
        return False
    print(f"Warning: {reason}; skipping freeze check.")
    return True


def _step_b(*, strict: bool) -> bool:
    minor = current_minor()

    fetch = subprocess.run(
        ["git", "fetch", "--tags", "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch.returncode != 0:
        stderr = fetch.stderr.strip() or f"exit code {fetch.returncode}"
        return _unverifiable(f"`git fetch --tags` failed ({stderr})", strict=strict)

    tags = _matching_release_tags(minor)
    if not tags:
        print(f"No v{minor}.* release tags found; freeze check not applicable yet.")
        return True

    lowest_tag = tags[0]
    target = snapshot_path(_FROZEN_SURFACE)
    rel_path = target.relative_to(REPO_ROOT).as_posix()

    # git resolves `tag:path` from the top of the repository, but rel_path is
    # relative to the backend directory. The `./` prefix makes git resolve it
    # from the working directory instead.
    show = subprocess.run(
        ["git", "show", f"{lowest_tag}:./{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if show.returncode != 0:
        return _unverifiable(f"{rel_path} not found at tag {lowest_tag}", strict=strict)

    tagged_content = show.stdout
    current_content = target.read_text()
    if tagged_content != current_content:
        print(
            f"pat API changed after v{minor} was released; bump the minor version in the "
            f"same pull request (`scripts/bump_version.sh {_next_minor(minor)}` at the "
            "repository root) and re-export (`poetry run python scripts/export_openapi.py`)"
        )
        return False

    print(f"{rel_path} still matches the snapshot frozen at {lowest_tag} (OK).")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when the freeze check cannot run (on by default when CI is set)",
    )
    args = parser.parse_args(argv)
    strict = args.strict or strict_by_default()

    if not _step_a():
        return 1
    if not _step_b(strict=strict):
        return 1
    print(f"OpenAPI snapshot check passed for v{current_minor()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
