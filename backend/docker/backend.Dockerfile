# ─── Builder ────────────────────────────────────────────────
# Poetry exists only here: it resolves the lockfile into /app/.venv, which
# the dev/prod stages put on PATH. The runtime stages never install or run
# poetry -- per-user poetry config (root vs the prod `glados` user) once
# made `poetry run` silently create a fresh empty venv for glados and
# crash every runtime command with ModuleNotFoundError.
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS builder

WORKDIR /app

# Build-scoped only: apt otherwise probes Dialog/Readline/Teletype and prints a
# wall of "unable to initialize frontend" noise before falling back to this
# anyway. An ENV would leak into the running container.
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# The same Poetry as CI (POETRY_VERSION in .github/workflows/ci.yml), the
# version that wrote poetry.lock; bump both together.
ARG POETRY_VERSION=2.4.1
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}" \
    && poetry config virtualenvs.in-project true \
    && poetry install --no-root --only main

# ─── Dev stage ──────────────────────────────────────────────
# Keeps poetry (inherited from builder) so `poetry add`/`poetry lock` work
# inside the container; the venv on PATH means the app commands themselves
# (uvicorn, alembic, python -m ...) run without a `poetry run` prefix,
# same as prod.
FROM builder AS dev
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN poetry install --no-root
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
COPY . .
EXPOSE 3000

# ─── Prod stage ─────────────────────────────────────────────
# Fresh base: no poetry, no pip toolchain, no gcc/libpq-dev -- just the
# ready-made venv from the builder. curl serves the HEALTHCHECK,
# postgresql-client provides pg_dump/pg_restore for the backup/restore CLI
# (and pulls in libpq5).
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS prod

WORKDIR /app

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Same absolute path as in the builder, so the venv's shebangs and
# pyvenv.cfg stay valid.
COPY --from=builder /app/.venv ./.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
# Not build metadata here: src/modules/platform/const.py reads [project].version out of it at
# import time, so every runtime entrypoint (gunicorn, alembic, the CLI) dies
# with FileNotFoundError if it is missing.
COPY pyproject.toml ./
RUN useradd --uid 1000 --create-home glados \
    && mkdir -p /app/media /app/logs /app/pre-migration-dumps \
    && chown -R glados:glados /app
USER glados
EXPOSE 3000

# A start runs the pre-migration dump and the migrations before gunicorn
# boots its workers, which can take minutes. Failed checks within the start
# period do not count and the first good one ends it, so a quick start is
# healthy within seconds while a slow one is not marked unhealthy, which
# would make Compose give up on the services that wait for the backend.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --start-interval=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1
