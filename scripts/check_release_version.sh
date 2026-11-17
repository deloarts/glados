#!/usr/bin/env bash
# Verify that the checked-out tree is ready to be released as X.Y.Z: the
# version is a 0.x version, backend/pyproject.toml and frontend/package.json
# both carry it, CHANGELOG.md has its section, and the tag vX.Y.Z does not
# exist on origin yet. Shared by ci.yml's release-check job, release.yml's
# guard and scripts/release_start.sh, so all three agree on what releasable
# means. Does not touch git state.
#
# Usage: scripts/check_release_version.sh X.Y.Z
set -euo pipefail

VERSION="${1:?usage: check_release_version.sh X.Y.Z}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

fail() {
  echo "::error::$1" >&2
  exit 1
}

# The major is fixed at 0, every contract change is a minor, see
# docs/RELEASING.md section 1.
[[ "$VERSION" =~ ^0\.[0-9]+\.[0-9]+$ ]] || fail "$VERSION is not a 0.Y.Z version"

backend_version="$(grep -m1 '^version' backend/pyproject.toml | sed -E 's/version = "(.*)"/\1/')"
frontend_version="$(node -p "require('./frontend/package.json').version")"
[[ "$backend_version" == "$VERSION" ]] || fail "backend/pyproject.toml has $backend_version, not $VERSION"
[[ "$frontend_version" == "$VERSION" ]] || fail "frontend/package.json has $frontend_version, not $VERSION"

grep -qE "^## \[${VERSION//./\\.}\]" CHANGELOG.md || fail "CHANGELOG.md has no '## [$VERSION]' section"

if git ls-remote --exit-code --tags origin "refs/tags/v$VERSION" >/dev/null; then
  fail "tag v$VERSION already exists on origin"
fi

echo "Ready to release $VERSION."
