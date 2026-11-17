#!/usr/bin/env bash
# Deploy the currently checked-out commit to the staging server:
# force-push it to the staging branch; CI builds the `staging` image.
# Usage: scripts/deploy_staging.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

git push --force origin HEAD:staging
echo "Pushed $(git rev-parse --short HEAD) to staging, image follows once CI is green."
