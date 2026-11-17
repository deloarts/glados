# developing

How to get a development machine running Glados, and the conventions every backend change follows. Sections 6 and 8 to 10 summarise the rules; the reference files they link to hold the complete rules.

- [developing](#developing)
  - [1 prerequisites](#1-prerequisites)
  - [2 install dependencies](#2-install-dependencies)
  - [3 configure the environment](#3-configure-the-environment)
    - [3.1 SolidWorks PDM connection (optional)](#31-solidworks-pdm-connection-optional)
  - [4 docker containers](#4-docker-containers)
    - [4.1 infrastructure only](#41-infrastructure-only)
    - [4.2 full stack](#42-full-stack)
    - [4.3 useful commands](#43-useful-commands)
    - [4.4 cloning staging data into the dev stack](#44-cloning-staging-data-into-the-dev-stack)
  - [5 service endpoints](#5-service-endpoints)
  - [6 database migrations](#6-database-migrations)
    - [6.1 writing migrations](#61-writing-migrations)
  - [7 release checks](#7-release-checks)
  - [8 datetime convention](#8-datetime-convention)
  - [9 test conventions](#9-test-conventions)
  - [10 writing async code](#10-writing-async-code)

## 1 prerequisites

- Python 3.13 or newer and [Poetry](https://python-poetry.org/), in the version named in the header of `backend/poetry.lock`.
- Node.js 22 (the major in `frontend/.nvmrc`) and npm.
- Docker with the Compose and Buildx plugins (`docker-compose-plugin`, `docker-buildx-plugin`). Without Buildx, Compose falls back to the deprecated legacy builder.
- `postgresql-client`, needed only when you run the backend directly on the host and test the backup feature (`pg_dump`, `psql`). The Docker image already includes it.

  ```bash
  sudo apt install postgresql-client
  ```

> [!NOTE]
> Running the backend directly on the host via Poetry/uvicorn is a
> development convenience only. Production deployments are Docker Compose
> only, see [INSTALLATION.md](INSTALLATION.md).

## 2 install dependencies

Backend commands in this doc (Poetry, pre-commit, migrations, OpenAPI export) assume `backend/` as the working directory:

```bash
cd backend
poetry install
poetry run pre-commit install
```

The git hooks run on every commit: gitleaks against committed secrets, ruff, mypy, import-linter, the OpenAPI and API types export, `plan-refs` and the frontend linters. Full rules, including the Poetry pin and gitleaks exceptions: [reference/development-environment.md](reference/development-environment.md).

Frontend commands in this doc assume `frontend/` as the working directory:

```bash
cd frontend
npm ci
```

Other useful scripts, also run from `frontend/`:

```bash
npm run dev         # Vite dev server with hot reload, http://localhost:5173
npm run build        # type-check, then build for production
npm run build-only   # build for production without the type-check
npm run test:unit    # run unit tests with Vitest
npm run test:coverage  # all unit tests with the coverage thresholds CI enforces
npm run lint         # oxlint + eslint, with --fix
```

`npm run dev` talks to the backend at `VITE_API_URL` (`frontend/.env.development`, defaults to `http://localhost:3000`), so either a host-run backend ([3](#3-configure-the-environment)) or the `backend` container ([4](#4-docker-containers)) needs to be up first.

**Recommended IDE setup:** [VS Code](https://code.visualstudio.com/) with the [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) extension (disable Vetur if it's installed). TypeScript can't type-check `.vue` imports on its own, so builds and CI use `vue-tsc` (`npm run type-check`); Volar gives the editor the same awareness.

## 3 configure the environment

Local development is configured through `.env.dev` at the repository root. Create it from the template, whose defaults work for a fully local setup (database, redis, security keys, system user seed):

```bash
cp .env.dev.example .env.dev
```

The template lists and comments the variables, which the app reads through `src/modules/platform/infrastructure/config/settings.py`. Docker Compose injects the file into the dev containers. To run the backend directly on the host instead, point it at the same file (from `backend/`, the file is one level up):

```bash
cd backend
ENV_FILE=../.env.dev poetry run uvicorn src.bootstrap.main:app --reload
```

Under the VS Code debugger (debugpy) the reloader often does not actually reload; if a change seems to have no effect, check the worker's start time in the log first. `DATABASE__URL` uses `localhost` for a host-run backend; a backend inside the Compose network uses the service name `postgres` instead.

Full rules: [reference/development-environment.md section 3](reference/development-environment.md#3-settings-and-env-files).

### 3.1 SolidWorks PDM connection (optional)

The SOLIDWORKS PDM Web API connection is an admin setting, not an environment variable. To point a dev backend at a real PDM Pro Web API server (default port 65453), open Settings → SolidWorks PDM as a user with `write:settings`, fill in the base URL, vault name and a service account, save, and use *Test connection* to confirm the vault answers. The same screen has an admin-only API console for troubleshooting, whose mutating operations stay refused unless the backend runs with `PDM__ALLOW_MUTATING_OPERATIONS=true` and its "Allow critical endpoints" switch is on for that visit, since Glados cannot undo them on a live vault. A host-run backend needs `poetry run alembic upgrade head` first ([6](#6-database-migrations)).

[PDM_INTEGRATION.md](PDM_INTEGRATION.md) covers the whole mechanism: the settings, the poller and the trigger endpoints, pre-release validation, the ingest rules, ownership enforcement, the generated Web API catalogue and the admin surfaces.

## 4 docker containers

All dev containers are defined in `docker-compose.dev.yml` and use `.env.dev` for their environment, both at the repository root; run the commands below from there (not from `backend/` or `frontend/`).

### 4.1 infrastructure only

Useful when running the backend directly via Poetry/uvicorn:

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev up postgres redis pgadmin seaweedfs -d
```

### 4.2 full stack

Runs the backend with hot-reload alongside the frontend, postgres, redis, and pgadmin:

```bash
# 1. Start infrastructure first and let it reach healthy state
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d postgres redis pgadmin seaweedfs

# 2. Build and start the application services
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d --build backend frontend
```

### 4.3 useful commands

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev ps              # container status
docker compose -f docker-compose.dev.yml --env-file .env.dev logs -f backend # tail logs
docker compose -f docker-compose.dev.yml --env-file .env.dev stop            # stop, keeps volumes/data
docker compose -f docker-compose.dev.yml --env-file .env.dev down            # stop and remove, keeps volumes/data
```

To also remove the volumes, which resets the database, redis and uploads:

> [!CAUTION]
> This command erases all data.

```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev down -v
```

### 4.4 cloning staging data into the dev stack

`scripts/sync_staging_to_dev.sh` replaces the local Postgres, Redis, SeaweedFS and media data with a copy of the staging server's, for reproducing a problem on real data:

```bash
STAGING_SSH_USER=<user> scripts/sync_staging_to_dev.sh <host>
```

It needs `.env.staging`, ssh key access and passwordless sudo on the host. For the length of the copy it stops staging's Postgres, Redis and SeaweedFS. Local data is lost, and `.env.dev` is rewritten from `.env.staging` with a backup of the old file. Full rules: [reference/development-environment.md section 4](reference/development-environment.md#4-cloning-staging-data).

## 5 service endpoints

| Service   | URL                    | Notes                                                                        |
| --------- | ---------------------- | ----------------------------------------------------------------------------- |
| Backend   | http://localhost:3000  | FastAPI, reload enabled                                                       |
| Frontend  | http://localhost:80    | nginx, built Vue app                                                         |
| Postgres  | localhost:5432         | user/db from `.env.dev`                                                      |
| pgAdmin   | http://localhost:5050  | login from `.env.dev` (`PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD`) |
| Redis     | localhost:6379         | `redis-cli -h localhost`                                                     |
| SeaweedFS S3 | http://localhost:8333 | S3-compatible API endpoint, bucket `objects`                              |
| SeaweedFS UI | http://localhost:23646 | admin UI, login from `.env.dev` (`SEAWEEDFS_ACCESS_KEY` / `SEAWEEDFS_SECRET_KEY`) |

To store files in SeaweedFS, pick it in Admin Settings → Storage with `http://localhost:8333` as both endpoint URL and public endpoint URL, bucket `objects` and the key pair from `.env.dev`.

## 6 database migrations

Alembic manages the schema. Whenever `DEBUG=true`, which `.env.dev` sets, the backend's lifespan migrates to head on start (`run_migrations()` in `src/bootstrap/adapters/outbound/persistence/init_db.py`). With `--reload` that also happens on every reload, so a file that lands in `alembic/versions/` is applied as soon as anything under `backend/src` changes. Outside Docker, apply migrations by hand from `backend/`:

```bash
poetry run alembic upgrade head     # apply everything pending
poetry run alembic downgrade -1     # roll back one revision
```

Containers started from a release image (staging today) run `alembic upgrade head` on every start, so a broken migration is a broken deployment, not just a failing dev command.

The history runs in one line from a single initial migration. Released migrations are immutable, since production databases have applied them, and every migration carries production data forward, so a database upgraded from any release holds what a fresh install would. A migration must never need a person to repair a database afterwards: nobody edits `alembic_version`, stamps a revision or reruns DDL by hand.

Full rules: [reference/development-migrations.md](reference/development-migrations.md).

### 6.1 writing migrations

Change the models first, then write the migration, either by hand in one go or as an autogenerated draft from `backend/`:

```bash
poetry run alembic check                                             # model changes no migration covers yet
poetry run alembic revision --autogenerate -m "add supplier rating"  # write a draft
```

A reloading dev backend applies a draft the moment anything under `backend/src` changes, so finish and review it before touching `src` again, or stop the dev backend while you write it. A migration keeps a single head, works on Postgres and SQLite, guards every create and drop with an inspection, names its constraints and never imports from `src`. A new key in a stored JSON settings value is added by a data migration that writes the key's default into every stored row. Check it by running the whole chain:

```bash
poetry run pytest tests/integration/test_alembic_migrations.py -q
```

Do not apply a migration to a shared or production database as part of writing it; an authored but unapplied migration on disk is normal.

Full rules: [reference/development-migrations.md section 3](reference/development-migrations.md#3-writing-a-migration).

## 7 release checks

CI compares the committed OpenAPI snapshots in `backend/openapi/` with the live schema (`scripts/check_openapi.py`), and the frontend's generated `src/core/api/generated/webSchema.ts` with the committed `web` snapshot (`npm run check:api-types`). Any change to a route or schema therefore re-exports both in the same commit:

```bash
poetry run python scripts/export_openapi.py   # from backend/
npm run generate:api-types                     # from frontend/
```

The `export-openapi` pre-commit hook runs both steps on every commit that touches `backend/`, so with the hooks installed this happens on its own. A release performs the same re-export on its `release/X.Y.Z` branch ([RELEASING.md section 2.2](RELEASING.md#22-cutting-a-release)); doing it with the change that touched the API leaves the release branch nothing to redo. A change to the `pat` contract after its minor was released needs a minor bump instead of a re-export ([RELEASING.md section 5](RELEASING.md#5-the-pat-snapshot-check)).

Full rules: [reference/releasing-ci.md section 2](reference/releasing-ci.md#2-the-pat-snapshot-check).

## 8 datetime convention

Every datetime is stored as UTC and timezone-aware and compared aware to aware. Code reads the current time through `now_utc()` or `today_utc()` in `src/shared_kernel/domain/services/clock.py`, never `datetime.now(UTC)`, so a test can freeze the clock with one patch. Every calendar day the app shows or filters by is a day of the tenant's timezone from the general settings, and there is no per-user timezone.

Full rules: [reference/development-datetime.md](reference/development-datetime.md).

## 9 test conventions

From `backend/`:

```bash
poetry run pytest tests/unit/path/test_x.py -q      # one file
poetry run pytest tests -q -k some_name             # by name
poetry run pytest tests -q                          # everything, serial, slow
```

`make test` at the repository root runs the whole suite in parallel, and `make test-fast` runs the quick loop of backend unit tests, smoke-marked integration tests and frontend unit tests. The suite needs no Redis and no Postgres: it runs on a throwaway SQLite file and in-process fakes, and points Redis at database 15 so a stray write never reaches a dev backend. Unset `ENV_FILE` before running tests. When writing a test, capture logs with `glados_caplog` (plain `caplog` sees nothing), build entities with `tests/factories.py`, and use the shared fakes in `tests/unit/fakes.py`.

The Postgres race tests in `tests/pg/` are opt-in and need an empty throwaway database, never the development one. With the infrastructure containers running ([4.1](#41-infrastructure-only)), create one and run them from `backend/`:

```bash
docker compose -f ../docker-compose.dev.yml --env-file ../.env.dev exec postgres \
  createdb -U glados glados_race
GLADOS_TEST_PG_URL=postgresql+psycopg://glados:<password>@localhost:5432/glados_race \
  poetry run pytest tests/pg -q
```

Full rules: [reference/development-testing.md](reference/development-testing.md).

## 10 writing async code

All I/O in the backend is async and the domain stays sync: ports, adapters, use cases and handlers are `async def`, and every call to them is awaited. Nothing may block the event loop, so a library without an async client and CPU-heavy work run through `anyio.to_thread.run_sync`. A session serves one operation at a time, and relationships never lazy-load. Why the backend is async: [ADR 0001](adr/0001-hexagonal-architecture-async-io.md).

Full rules: [reference/development-async.md](reference/development-async.md).
