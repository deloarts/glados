#!/bin/sh
set -e

# Out-of-process CLI commands, dispatched before migrations run: recovery
# must work even when the schema is mid-upgrade, and `restore` in
# particular must not migrate the database it is about to replace.
# `maintenance` is the sidecar profile's command (docker-compose.yml /
# docker-compose.dev.yml, service "maintenance"): it never migrates and
# never touches the app, just blocks forever so a Portainer console (or
# `docker compose exec`) has somewhere to run `restore`/`admin` from
# without the live backend's connections in the way. `sleep infinity` is
# coreutils, present on python:3.13-slim (the base image, see
# docker/backend.Dockerfile) without adding a package.
# Allowlisted explicitly, never dispatch an arbitrary module name.
case "$1" in
  restore|admin)
    cmd="$1"
    shift
    # A one-off command is no gunicorn worker, so it keeps its metrics in
    # process memory. Left set, prometheus_client would write them into a
    # multiprocess directory that only the server start below creates, and
    # the command would fail on loading the app.
    unset PROMETHEUS_MULTIPROC_DIR
    exec python -m "src.bootstrap.cli.${cmd}" "$@"
    ;;
  maintenance)
    exec sleep infinity
    ;;
esac

# Prometheus multiprocess mode: create the directory before migrations
# run, not after -- if anything
# Alembic imports along the way ends up importing prometheus_client with
# this env var already set (see src/read/adapters/inbound/api/metrics.py's
# module docstring), prometheus_client's multiprocess mode requires the
# directory to already exist, it does not create it itself. Today's
# alembic/env.py imports only
# src.modules.platform.adapters.outbound.persistence.alembic_imports (ORM
# models), .models.base.Base and
# src.modules.platform.infrastructure.config.settings.cfg -- none of which import
# prometheus_client -- but this stays a defensive ordering (mkdir always
# happens, not conditional on "does anything actually touch it today")
# rather than something that would break the moment that import graph
# changes. No-op when the env var isn't set (dev's single-process uvicorn
# never sets it).
if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
  mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

# Dump the database before pending migrations change it, so a migration
# that destroys or garbles data can be undone with `restore --file`. The
# command decides itself whether anything is pending and writes nothing
# when not. A failed dump stops the start instead of migrating without a
# way back; GLADOS_SKIP_PRE_MIGRATION_DUMP=true skips the dump for an
# operator who has taken one by other means (docs/OPERATIONS.md section 3.1).
if [ "${GLADOS_SKIP_PRE_MIGRATION_DUMP:-false}" = "true" ]; then
  echo "GLADOS_SKIP_PRE_MIGRATION_DUMP=true: migrating without a pre-migration dump." >&2
elif ! python -m src.bootstrap.cli.admin pre-migration-dump; then
  echo "ERROR: the pre-migration dump failed, so no migration was applied and the" >&2
  echo "backend does not start. Fix the cause above, or set" >&2
  echo "GLADOS_SKIP_PRE_MIGRATION_DUMP=true to migrate without a dump." >&2
  exit 1
fi

# Concurrent starts are safe: alembic/env.py holds an advisory lock while it
# migrates, so a second container waits and then finds nothing to do.
alembic upgrade head

# Wipe right before exec'ing the real command, not before migrations: the
# master starts every gunicorn boot with a clean directory, so *.db files
# left behind by a previous container run (a different set of pids), or by
# whatever ran under this same pid during the migration step above, can
# never be summed into this run's gauges/counters.
if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
  rm -rf "$PROMETHEUS_MULTIPROC_DIR"/*
fi

exec "$@"
