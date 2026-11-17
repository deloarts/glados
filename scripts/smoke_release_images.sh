#!/usr/bin/env bash
# Start the backend and frontend images the way an operator does, before
# they are published: the release docker-compose.yml with an empty Postgres and
# Redis, throwaway secrets and the two images pinned by the caller. The
# backend's entrypoint migrates the empty database, and the check passes
# once the backend answers /health with the expected version and /ready with
# 200, nginx accepts its configuration, and the frontend serves index.html
# and proxies /health and /ready to the backend. The stack and its volumes
# are removed afterwards, also on failure, which prints the containers' logs
# first. Used by release.yml's smoke job; runs locally against any two
# images, a local build included.
#
# Usage: scripts/smoke_release_images.sh BACKEND_IMAGE FRONTEND_IMAGE [VERSION]
#
#   BACKEND_IMAGE, FRONTEND_IMAGE   image references, by digest in CI
#   VERSION                         the version /health must report (optional)
#   SMOKE_FRONTEND_PORT             host port of the frontend (default 18080)
#   SMOKE_TIMEOUT                   seconds the stack may take to become
#                                   healthy, migrations included (default 600)
set -euo pipefail

USAGE="usage: smoke_release_images.sh BACKEND_IMAGE FRONTEND_IMAGE [VERSION]"
BACKEND_IMAGE="${1:?$USAGE}"
FRONTEND_IMAGE="${2:?$USAGE}"
EXPECTED_VERSION="${3:-}"
PORT="${SMOKE_FRONTEND_PORT:-18080}"
TIMEOUT="${SMOKE_TIMEOUT:-600}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
PROJECT="glados-smoke-$$"

fail() {
  echo "::error::$1" >&2
  exit 1
}

key() {
  openssl rand -hex 32
}

# No profile may start a sidecar (pgAdmin, SeaweedFS) in the smoke stack.
unset COMPOSE_PROFILES

# Every value is a throwaway one, made for this run only. The keys are
# distinct and long enough for the backend's boot guard, which refuses
# placeholders outside debug mode.
db_password="$(key)"
cat >"$WORK/smoke.env" <<EOF
GLADOS_VERSION=smoke
FRONTEND_PORT=$PORT
DEBUG=false
DOMAIN=http://127.0.0.1:$PORT
LOG_LEVEL=INFO
DATABASE__URL=postgresql+psycopg://glados:$db_password@postgres:5432/glados
POSTGRES_USER=glados
POSTGRES_PASSWORD=$db_password
POSTGRES_DB=glados
REDIS__URL=redis://redis:6379/0
SECURITY__SECRET_KEY_PERSISTENT=$(key)
SECURITY__SECRET_KEY_NON_PERSISTENT=$(key)
SECURITY__ENCRYPTION_KEY=$(key)
SECURITY__BACKUP_ENCRYPTION_KEY=$(key)
INIT__FULL_NAME=Smoke Test
INIT__MAIL=smoke@example.com
INIT__PASSWORD=$(key)
EOF

# The release compose file names the images by tag; this override pins the
# two images under test instead, so the stack runs exactly them.
cat >"$WORK/images.yml" <<EOF
services:
  backend:
    image: $BACKEND_IMAGE
  frontend:
    image: $FRONTEND_IMAGE
EOF

compose() {
  ENV_FILE="$WORK/smoke.env" docker compose \
    --project-name "$PROJECT" \
    --env-file "$WORK/smoke.env" \
    --file "$REPO_ROOT/docker-compose.yml" \
    --file "$WORK/images.yml" \
    "$@"
}

ok=false
cleanup() {
  if [[ "$ok" != true ]]; then
    echo "Smoke test failed; the stack's state and logs follow." >&2
    compose ps --all >&2 || true
    compose logs --no-color >&2 || true
  fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "Starting $BACKEND_IMAGE and $FRONTEND_IMAGE on an empty database."
compose up --detach --wait --wait-timeout "$TIMEOUT" ||
  fail "The stack did not become healthy within ${TIMEOUT}s."

health="$(compose exec -T backend curl -fsS http://localhost:3000/health)" ||
  fail "The backend does not answer /health."
echo "backend /health: $health"
if [[ -n "$EXPECTED_VERSION" && "$health" != *"\"version\":\"$EXPECTED_VERSION\""* ]]; then
  fail "The backend reports $health, not version $EXPECTED_VERSION."
fi

ready="$(compose exec -T backend curl -fsS http://localhost:3000/ready)" ||
  fail "The backend's /ready does not answer 200: $(compose exec -T backend curl -sS http://localhost:3000/ready || true)"
echo "backend /ready: $ready"

compose exec -T frontend nginx -t || fail "nginx refuses the frontend's configuration."

index="$(curl -fsS "http://127.0.0.1:$PORT/")" || fail "The frontend does not serve /."
[[ "$index" == *'<div id="app"></div>'* ]] || fail "The frontend's / is not the app's index.html."

curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null || fail "The frontend does not proxy /health."
curl -fsS "http://127.0.0.1:$PORT/ready" >/dev/null || fail "The frontend does not proxy /ready."

ok=true
echo "Smoke test passed."
