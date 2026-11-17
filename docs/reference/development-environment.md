# development environment

The exact rules behind the local development setup: toolchain pins, the git hooks, how settings are read, and what the staging clone script changes. [DEVELOPMENT.md](../DEVELOPMENT.md) walks through the setup itself.

- [development environment](#development-environment)
  - [1 toolchain pins](#1-toolchain-pins)
  - [2 git hooks](#2-git-hooks)
  - [3 settings and env files](#3-settings-and-env-files)
  - [4 cloning staging data](#4-cloning-staging-data)

## 1 toolchain pins

- The Poetry version is the one named in the header of `backend/poetry.lock`. CI pins the same version (`POETRY_VERSION` in `.github/workflows/ci.yml`), and so does the image build (the `POETRY_VERSION` argument of `backend/docker/backend.Dockerfile`).
- When the lock is regenerated with a newer Poetry, raise both pins in the same change.
- Node.js is 22, the major in `frontend/.nvmrc` that CI and the frontend image use. `engines` in `frontend/package.json` asks for 22.22.2 or newer.

## 2 git hooks

`.pre-commit-config.yaml` defines the hooks that `poetry run pre-commit install` sets up. They run on every commit:

- gitleaks scans the staged changes and blocks committed secrets. The hook builds its binary on first use, which takes a moment once.
- ruff lint, ruff format and mypy run from the Poetry environment, so with the versions in `poetry.lock`, over the same scope as CI.
- import-linter runs for `backend/` changes.
- `export-openapi` re-exports the OpenAPI snapshots and regenerates the API types for `backend/` changes.
- `pdm-catalogue` runs `generate.py --check` when either side of the PDM Web API catalogue changes and fails when `catalogue.py` no longer matches `operations.json`. A hand edit to the catalogue itself is lost the next time it is generated.
- `plan-refs` runs `scripts/check_plan_refs.py`, which rejects planning labels in comments and docs, for source, script and doc changes.
- The frontend linters run for `frontend/` changes.

A gitleaks finding that is a deliberate test value is allowed through a `.gitleaksignore` file at the repository root, one fingerprint per line as gitleaks prints it. gitleaks reads the file on its own, both in the hook and in CI. The file does not exist yet; create it with the first such exception.

## 3 settings and env files

- All app settings are read by the `pydantic-settings` model in `backend/src/modules/platform/infrastructure/config/settings.py`, with `__` as the nesting delimiter. `.env.dev.example` lists and comments the variables a local setup uses.
- `.env.dev` also holds compose-only variables that are not part of the settings model (`POSTGRES_*`, `PGADMIN_*`, `SEAWEEDFS_*`). Compose injects them directly into the relevant containers via `env_file:`.
- With `docker compose`, all variables are injected via `env_file: .env.dev` in `docker-compose.dev.yml`. A host-run backend reads the same file through `ENV_FILE=../.env.dev`.
- `DATABASE__URL` uses `localhost` for host execution and the service name `postgres` inside the Compose network.
- `DATABASE__URL` names the psycopg 3 driver, `postgresql+psycopg://glados:change_me@localhost:5432/glados_dev`.
- The app and Alembic always connect through `DATABASE__URL`.

## 4 cloning staging data

`scripts/sync_staging_to_dev.sh <host>` needs and does the following:

- It needs `.env.staging` at the repository root, ssh key access and passwordless sudo on the host, rsync on both ends and sudo locally.
- A running host uvicorn has to be stopped first.
- After a confirmation prompt it stops the local infra containers and, for the length of the copy, staging's Postgres, Redis and SeaweedFS, so the copied data directories are consistent.
- It rsyncs the volumes into `.volumes/` and `backend/media`.
- It rewrites `.env.dev` from `.env.staging` with the dev overrides and keeps the old file as `.env.dev.bak.<timestamp>`.
- It recreates the local containers and points the copied storage settings at the local SeaweedFS port.
- Local data is lost. The backend applies any migrations newer than staging's on its next start.
