#!/usr/bin/env bash
# Clone the staging server's data into the local dev stack: copies the Postgres,
# Redis, SeaweedFS and media volumes over ssh, rewrites
# .env.dev from .env.staging with the dev-only overrides, and recreates the local
# infra containers so they bind to this repo's .volumes/ directory.
#
# Staging Postgres, Redis and SeaweedFS are stopped for the duration of the copy
# so the data directories are consistent, then started again. Local data is
# replaced.
#
# Usage: STAGING_SSH_USER=<user> scripts/sync_staging_to_dev.sh <host>
# The host can also be given as STAGING_HOST.
# Requires: ssh key access to the host (a passphrase is asked once, the
# connection is reused), passwordless sudo on the host, rsync on both ends,
# sudo locally (volume directories are owned by the container uids).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

HOST="${1:-${STAGING_HOST:?pass the staging host as argument or STAGING_HOST}}"
SSH_USER="${STAGING_SSH_USER:?set STAGING_SSH_USER to the ssh login on the staging host}"
REMOTE="$SSH_USER@$HOST"
COMPOSE=(docker compose -f docker-compose.dev.yml --env-file .env.dev)
VOLUMES_DIR="$REPO_ROOT/.volumes"

# Staging named volume -> local bind-mount directory. media goes to backend/media
# because the dev backend runs on the host with LOCAL_STORAGE__BASE_DIR=./media.
declare -A TARGETS=(
  [glados_postgres]="$VOLUMES_DIR/postgres"
  [glados_redis]="$VOLUMES_DIR/redis"
  [glados_seaweedfs]="$VOLUMES_DIR/seaweedfs"
  [glados_media]="$REPO_ROOT/backend/media"
)

# One multiplexed ssh connection for the whole run, so a key passphrase is
# entered once instead of on every ssh and rsync call.
SSH_OPTS=(-o ControlMaster=auto -o ControlPath="/tmp/glados-sync-%r@%h:%p" -o ControlPersist=10m)
remote() { ssh "${SSH_OPTS[@]}" "$REMOTE" "$@"; }

[[ -f .env.staging ]] || { echo ".env.staging not found in $REPO_ROOT" >&2; exit 1; }

if pgrep -f "uvicorn src.bootstrap.main:app" >/dev/null; then
  echo "A local uvicorn is running; stop it first (it holds database connections)." >&2
  exit 1
fi

step=""
fail() { [[ $? -eq 0 ]] || echo "FAILED at: $step" >&2; }
trap fail ERR

step="checking staging access"
remote 'sudo -n true' || { echo "Need passwordless sudo on $HOST" >&2; exit 1; }
mapfile -t REMOTE_VOLUMES < <(remote 'docker volume ls --format "{{.Name}}"' | grep -E '^glados_(postgres|redis|seaweedfs|media)$')
[[ ${#REMOTE_VOLUMES[@]} -gt 0 ]] || { echo "No glados volumes found on $HOST" >&2; exit 1; }
echo "Staging volumes: ${REMOTE_VOLUMES[*]}"

# Staging runs as a Portainer stack whose compose file lives inside the Portainer
# container, so `docker compose` is unavailable on the host. Address the
# containers by their compose labels instead.
step="finding staging postgres/redis containers"
mapfile -t STAGING_CONTAINERS < <(remote 'docker ps -aq --filter label=com.docker.compose.project=glados --filter label=com.docker.compose.service=postgres; docker ps -aq --filter label=com.docker.compose.project=glados --filter label=com.docker.compose.service=redis')
[[ ${#STAGING_CONTAINERS[@]} -eq 2 ]] || { echo "Expected postgres and redis containers on $HOST, found: ${STAGING_CONTAINERS[*]:-none}" >&2; exit 1; }
# A running SeaweedFS is stopped and restarted with them; its filer metadata
# is not safe to copy while it writes.
mapfile -t -O 2 STAGING_CONTAINERS < <(remote 'docker ps -q --filter label=com.docker.compose.project=glados --filter label=com.docker.compose.service=seaweedfs')

step="local sudo"
sudo -v || { echo "Local sudo is required (volume directories are owned by container uids)." >&2; exit 1; }

echo
echo "This replaces the local dev database, Redis, object storage and media with staging's copy,"
echo "rewrites .env.dev, and briefly stops Postgres/Redis/SeaweedFS on $HOST."
read -r -p "Continue? [y/N] " answer
[[ "$answer" == [yY] ]] || exit 1

# Local containers must not be running while their data directories are
# overwritten, or they corrupt the copy on shutdown.
step="stopping local infra containers"
"${COMPOSE[@]}" stop

step="stopping staging postgres/redis/seaweedfs"
remote "docker stop ${STAGING_CONTAINERS[*]}"
trap 'rc=$?; [[ $rc -eq 0 ]] || echo "FAILED at: $step" >&2; echo "Restarting staging postgres/redis/seaweedfs..."; remote "docker start ${STAGING_CONTAINERS[*]}"; ssh "${SSH_OPTS[@]}" -O exit "$REMOTE" 2>/dev/null || true' EXIT
trap - ERR

for vol in "${REMOTE_VOLUMES[@]}"; do
  target="${TARGETS[$vol]}"
  step="syncing $vol"
  source_dir="$(remote "docker volume inspect --format '{{.Mountpoint}}' $vol")"
  echo "Syncing $vol ($source_dir) -> $target"
  sudo mkdir -p "$target"
  sudo rsync -a --delete --rsync-path="sudo rsync" -e "ssh ${SSH_OPTS[*]}" \
    "$REMOTE:$source_dir/" "$target/"
done
step="creating log/media directories"
sudo mkdir -p "$VOLUMES_DIR/logs" "$VOLUMES_DIR/media"
sudo chown "$USER:$USER" "$VOLUMES_DIR" "$VOLUMES_DIR/logs" "$VOLUMES_DIR/media"
# The dev backend runs on the host as this user and writes uploads here.
sudo chown -R "$USER:$USER" "$REPO_ROOT/backend/media"

step="recreating local containers"
echo "Removing local infra containers..."
"${COMPOSE[@]}" down --remove-orphans

step="writing .env.dev"
echo "Writing .env.dev from .env.staging..."
[[ -f .env.dev ]] && cp .env.dev ".env.dev.bak.$(date +%Y%m%d%H%M%S)"
pg_pw="$(grep -E '^POSTGRES_PASSWORD=' .env.staging | cut -d= -f2-)"
pg_db="$(grep -E '^POSTGRES_DB=' .env.staging | cut -d= -f2-)"
{
  grep -vE '^(DEBUG|DOMAIN|DATABASE__URL|REDIS__URL|COMPOSE_PROFILES|GLADOS_VERSION|ENV_FILE|PGADMIN_DEFAULT_EMAIL|PGADMIN_DEFAULT_PASSWORD)=' .env.staging
  cat <<EOF

# dev overrides (written by scripts/sync_staging_to_dev.sh)
DEBUG=true
DOMAIN=http://localhost:5173
DATABASE__URL=postgresql+psycopg://glados:${pg_pw}@localhost:5432/${pg_db}
REDIS__URL=redis://localhost:6379/0
PGADMIN_DEFAULT_EMAIL=admin@localhost.local
PGADMIN_DEFAULT_PASSWORD=admin
EOF
} > .env.dev

services=(postgres redis)
[[ -d "$VOLUMES_DIR/seaweedfs" ]] && services+=(seaweedfs)
echo "Starting local ${services[*]}..."
"${COMPOSE[@]}" up -d --force-recreate "${services[@]}"

# The storage settings row came from staging and points at the compose-internal
# storage hostname and staging's reverse proxy. The dev backend runs on the host,
# so both must be the published local port.
step="repointing storage settings"
pg_user="$(grep -E '^POSTGRES_USER=' .env.staging | cut -d= -f2-)"
until docker exec glados-postgres-1 pg_isready -q -U "$pg_user" -d "$pg_db"; do sleep 1; done
docker exec glados-postgres-1 psql -q -U "$pg_user" -d "$pg_db" -c \
  "update admin_storage_settings set endpoint_url = 'http://localhost:8333', public_endpoint_url = 'http://localhost:8333' where provider = 'seaweedfs';"

echo "Done. Start the backend with: cd backend && ENV_FILE=../.env.dev poetry run uvicorn src.bootstrap.main:app --reload"
echo "It will replay any migrations newer than staging's on first boot."
