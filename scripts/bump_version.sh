#!/usr/bin/env bash
# Bump the whole monorepo to one version: backend/pyproject.toml and
# frontend/package.json (+ package-lock.json). Idempotent - running it again
# with the same version is a no-op change. Does NOT touch git.
#
# Usage: scripts/bump_version.sh X.Y.Z
set -euo pipefail

VERSION="${1:?usage: bump_version.sh X.Y.Z}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not a X.Y.Z version: $VERSION" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(cd "$REPO_ROOT/backend" && poetry version "$VERSION")
(cd "$REPO_ROOT/frontend" && npm version "$VERSION" --no-git-tag-version --allow-same-version)

BACKEND_VERSION="$(cd "$REPO_ROOT/backend" && poetry version -s)"
FRONTEND_VERSION="$(cd "$REPO_ROOT/frontend" && node -p "require('./package.json').version")"

echo "backend:  $BACKEND_VERSION"
echo "frontend: $FRONTEND_VERSION"
