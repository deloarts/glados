#!/usr/bin/env bash
# Start a release: branch release/X.Y.Z from an up-to-date main, bump both
# halves' version, regenerate the OpenAPI snapshots and the frontend API
# types, open a CHANGELOG section, commit and push. Merging the release PR
# into main is what tags and publishes the release (release.yml).
#
# Running it for a version main already carries (a feature PR that changed
# the pat surface bumps the minor itself) is fine, only the CHANGELOG
# section is new then.
#
# Usage: scripts/release_start.sh X.Y.Z
set -euo pipefail

VERSION="${1:?usage: release_start.sh X.Y.Z}"
[[ "$VERSION" =~ ^0\.[0-9]+\.[0-9]+$ ]] || { echo "not a 0.Y.Z version: $VERSION" >&2; exit 1; }
BRANCH="release/$VERSION"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

[[ -z "$(git status --porcelain)" ]] || { echo "working tree is not clean" >&2; exit 1; }

git checkout main
git pull --ff-only

if git show-ref --verify --quiet "refs/heads/$BRANCH" \
  || git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null; then
  echo "branch $BRANCH already exists" >&2
  exit 1
fi
if git ls-remote --exit-code --tags origin "refs/tags/v$VERSION" >/dev/null; then
  echo "tag v$VERSION already exists" >&2
  exit 1
fi

git checkout -b "$BRANCH"

"$REPO_ROOT/scripts/bump_version.sh" "$VERSION"

(cd "$REPO_ROOT/backend" && poetry run python scripts/export_openapi.py)
(cd "$REPO_ROOT/frontend" && npm run generate:api-types)

# Everything under [Unreleased] becomes this version's section, and a fresh
# empty [Unreleased] heading stays on top.
if ! grep -qE "^## \[${VERSION//./\\.}\]" CHANGELOG.md; then
  sed -i "0,/^## \[Unreleased\]$/s//## [Unreleased]\n\n## [$VERSION] - $(date -u +%Y-%m-%d)/" CHANGELOG.md
fi

git add backend/pyproject.toml frontend/package.json frontend/package-lock.json \
  backend/openapi frontend/src/core/api/generated CHANGELOG.md
if ! git diff --quiet -- backend/poetry.lock; then
  git add backend/poetry.lock
fi
if git diff --cached --quiet; then
  echo "Nothing to commit, main already carries $VERSION and its CHANGELOG section."
else
  git commit -m "release: $VERSION"
fi

"$REPO_ROOT/scripts/check_release_version.sh" "$VERSION"

git push -u origin "$BRANCH"

echo
echo "Next: review CHANGELOG.md on $BRANCH, then open the PR into main:"
echo "  gh pr create --base main --head $BRANCH --title \"release: $VERSION\""
echo "Merging it tags v$VERSION and publishes the images."
