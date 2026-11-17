---
description: Run the tests and quality gates relevant to the current changes
argument-hint: [path | pattern | all | backend | frontend | ci]
---

Run the relevant tests and quality gates for the current work. Follow these steps.

## 1. Determine scope

Arguments given: `$ARGUMENTS`

- If `$ARGUMENTS` is empty: inspect `git status` and scope by path prefix, `backend/` vs
  `frontend/`. Map changed backend files (`backend/src/...`) to their matching `backend/tests/`
  modules; map changed frontend files (`frontend/src/...`) to their colocated
  `__tests__/*.spec.ts`. Run the backend gates for any changed backend files and the frontend
  type-check/lint for any changed frontend files; run `check:i18n` only if locale files
  (`frontend/src/core/i18n/locales/*.ts`) changed; run `check:api-types` only if
  `frontend/src/core/api/generated/webSchema.ts` or API type files under
  `frontend/src/features/*/types/` changed.
- Image builds: after the checks pass, CI builds both Docker images, and a build can fail where
  every gate passed (the frontend build type-checks cold under a fixed heap limit). Run the
  frontend image check (step 2) for `all` and `frontend`, and in the default scope when
  `frontend/package.json`, `frontend/package-lock.json`, a `frontend/tsconfig*.json`,
  `frontend/vite.config.ts` or anything under `frontend/docker/` changed. Run the Docker builds
  (step 2) for `all`, and in the default scope when a Dockerfile, a `.dockerignore`, anything
  under `backend/docker/` or `frontend/docker/`, or a dependency manifest
  (`frontend/package.json`, `frontend/package-lock.json`, `backend/pyproject.toml`,
  `backend/poetry.lock`) changed.
- If `$ARGUMENTS` is `ci`: skip the rest of this step and step 2, follow step 4 instead, and
  report as in step 3.
- If `$ARGUMENTS` is `all`: run the full gate set for both halves.
- If `$ARGUMENTS` is `backend` or `frontend`: run the full gate set, scoped to that one half only.
- Otherwise treat `$ARGUMENTS` as a path or pattern: target it directly (a backend test
  path/expression, or a frontend spec path). Still run the gates for the affected half.

## 2. Run commands

Backend (`cd backend`):
- Full run in parallel, then the serial parts:
  `poetry run pytest tests -q -n auto --maxprocesses 15 -m "not benchmark" --ignore tests/pg`,
  `poetry run pytest tests -q -m benchmark` and `poetry run pytest tests/pg -q` (as `make test`
  does); or a targeted path when scoped, e.g. `poetry run pytest tests/unit/test_order_use_cases.py -q`
- `poetry run ruff check src tests scripts alembic`
- `poetry run ruff format --check src tests scripts alembic`
- `poetry run mypy src scripts`
- `poetry run lint-imports`

Frontend (`cd frontend`):
- `npm run test:unit:run`, with a path filter when scoped, e.g. `npm run test:unit:run -- src/features/orders/components/__tests__/OrdersTable.spec.ts`
- `npm run type-check`
- `npm run lint:check`
- `npm run check:i18n`, only if locale files changed
- `npm run check:api-types`, only if generated API types or matching feature types changed
- Image check (see step 1 for when): `NODE_OPTIONS=--max-old-space-size=6144 npx vue-tsc --build --force`,
  then `npm run build-only`. The `--force` is the point: `npm run type-check` reuses the
  incremental cache in `node_modules/.tmp` and needs far less memory than the cold run inside the
  image, so it cannot catch a heap overflow. Keep the limit equal to the `NODE_OPTIONS` in
  `frontend/docker/frontend.Dockerfile`.

Docker images (repo root, see step 1 for when), the same builds `ci.yml` and `release.yml` run:
- `docker build --build-arg VITE_API_URL= -t glados-frontend:test-check -f frontend/docker/frontend.Dockerfile frontend`
- `docker build --target prod -t glados-backend:test-check -f backend/docker/backend.Dockerfile backend`
- Afterwards remove the tags: `docker image rm glados-frontend:test-check glados-backend:test-check`.
  If Docker is not running, report that as a gate that could not run.
- These build the working tree, so a file saved halfway through an edit ends up in the image.
  `ci` builds the committed `HEAD` instead.

Skip a half entirely if scope excludes it (no changes there, or `backend`/`frontend` argument
narrowed to the other).

## 3. Report honestly

- Report failures verbatim, including file:line from the tool output. Do not paraphrase or summarize away a stack trace.
- No hedging like "mostly passing" or "just a couple of flaky failures". State the pass/fail count and list every failure.
- Never "fix" a failing test by changing the test itself to make it pass. If a test looks wrong, flag it explicitly and ask before touching it. This is a hard project rule.
- If a gate could not run (e.g. that half's dependencies not installed), say so plainly instead of skipping silently.

## 4. CI replica (`ci`)

Runs what `.github/workflows/ci.yml` runs on a push to `staging`, where every job runs whatever
the path filter says. It takes 30 minutes or more and cannot be scoped. It differs from the
other modes in three ways, each of which let a CI failure slip past a local run:

- It tests a clean clone of the committed `HEAD`, never the working tree. If `git status` shows
  uncommitted changes, say in the report that they were not tested.
- It installs from the lockfiles into an empty directory, so no warm `node_modules`, virtualenv
  or `tsbuildinfo` cache hides a failure. A warm incremental type-check needs far less memory
  than CI's cold one.
- The frontend runs in a `node` container without network, and the backend tests see no Redis,
  as on the runner. Locally the dev backend on port 3000 answers a request a spec forgot to
  mock, and the dev Redis answers the backend tests.

Keep going after a failing job, CI runs and reports them all. Commands run in `$CI_DIR` (or the
named subdirectory) unless noted.

### Setup

1. From the repo root: `git fetch --tags origin` (the OpenAPI check reads release tags), then
   clone into a new empty directory in the session scratchpad, or `mktemp -d` when there is
   none: `git clone --quiet . "$CI_DIR"` and `git -C "$CI_DIR" checkout --quiet --detach "$(git rev-parse HEAD)"`.
2. A throwaway Postgres like CI's service, on a port clear of the dev one:
   `docker run -d --rm --name glados-ci-postgres -e POSTGRES_USER=glados_ci -e POSTGRES_PASSWORD=glados_ci -e POSTGRES_DB=glados_ci -p 127.0.0.1:55432:5432 postgres:16`,
   then wait until `docker exec glados-ci-postgres pg_isready -U glados_ci` succeeds. It starts
   empty, which the migration test's safety guard requires. Never point `GLADOS_TEST_PG_URL` at
   any other database.
3. The frontend container, used below as `NODE_RUN`:
   `docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e NODE_OPTIONS=--max-old-space-size=6144 -v "$CI_DIR:/repo" -w /repo/frontend node:22`,
   with the major version from `frontend/.nvmrc` and the heap limit from `frontend-verify`.

If Docker is not running, the setup cannot be done; report that and stop.

### Jobs

- **publish-channel-image**, built first while the clone is still untouched by installs and
  test output (CI builds it last, and only when every check passed; say so if a check failed):
  `docker build --build-arg VITE_API_URL= -t glados-frontend:ci-check -f frontend/docker/frontend.Dockerfile frontend`
  and `docker build --target prod -t glados-backend:ci-check -f backend/docker/backend.Dockerfile backend`.
- **version-parity**: the `version` in `backend/pyproject.toml` must equal the one in
  `frontend/package.json`, read the way the job's script reads them.
- **plan-refs**: `python3 scripts/check_plan_refs.py`.
- **gitleaks**: download the release named by `GITLEAKS_VERSION` in `ci.yml`, verify it against
  `GITLEAKS_SHA256` and unpack it, all as the job does, into `$CI_DIR/.ci-bin`. Then
  `.ci-bin/gitleaks git --redact --no-banner --verbose .`.
- **release-check**: only when the current branch is `release/X.Y.Z`, from the repo root:
  `scripts/check_release_version.sh X.Y.Z`, `git fetch origin main` and
  `git merge-base --is-ancestor origin/main HEAD`. Otherwise report it as skipped, as CI does.
- **quick-checks**: in `backend/`, `poetry install --no-interaction`,
  `poetry run ruff check src tests scripts alembic`, `poetry run ruff format --check src tests scripts alembic`,
  `poetry run lint-imports` and `poetry run pytest $(poetry run python scripts/select_tests.py --guards) -q`
  (with the `REDIS__URL` of backend-tests). In `frontend/`, through `NODE_RUN`: `npm ci`, then with
  `--network none` `npm run lint:check`, `npm run check:i18n` and `npm run test:guards`. CI skips
  backend-tests and the frontend unit tests when this job fails; here, run them anyway and say so.
- **backend-tests** (`backend/`): the four shards one after another, never in parallel, for N
  from 1 to 4:
  `GLADOS_TEST_PG_URL=postgresql+psycopg://glados_ci:glados_ci@localhost:55432/glados_ci REDIS__URL=redis://localhost:1/15 COVERAGE_FILE=.coverage.shardN poetry run pytest tests --ignore=tests/pg --splits 4 --group N --splitting-algorithm least_duration -q --cov=src --cov-report= --cov-fail-under=0 --hypothesis-profile ci`.
  CI starts no Redis, so `REDIS__URL` names a port where nothing listens.
- **backend-verify** (`backend/`), in the job's order:
  `poetry run python -m pip install --upgrade pip pip-audit` and `poetry run pip-audit --skip-editable`;
  `poetry run mypy src scripts`;
  `poetry run complexipy src --max-complexity-allowed 25 --failed`;
  `poetry run python scripts/check_function_length.py` (a report, it never fails);
  `poetry run coverage combine .coverage.shard*` and `poetry run coverage report`
  (`fail_under` is in `pyproject.toml`); `poetry run python scripts/check_openapi.py`;
  `poetry run alembic heads` must list exactly one `(head)`.
- **frontend-verify** (`frontend/`, through `NODE_RUN`): `npm ci`,
  `npm audit --omit=dev --audit-level=high`, and `npm audit --audit-level=high`, which only
  warns. Then with `--network none` added to `NODE_RUN`: `npm run type-check`,
  `npm run test:coverage`, `npm run build-only`.
  Vitest fails the run on unhandled errors even when every test passed; report them like
  failures.
- **api-types**: `poetry run python scripts/export_openapi.py --check` in `backend/`, then
  `npm run check:api-types` through `NODE_RUN` with `--network none`. CI runs its own `npm ci`
  first; the lockfile is the same, so the install from frontend-verify serves.

When `ci.yml` changes a job, change this list with it.

### Cleanup

Always, also after a failure: `docker stop glados-ci-postgres`,
`docker image rm glados-frontend:ci-check glados-backend:ci-check`,
`poetry env remove --all` in `$CI_DIR/backend` (the virtualenv lives outside the clone), then
delete `$CI_DIR`.

### Report

One line per CI job, as `gh run view` lists them: passed, failed or skipped, with every failure
reported in full as step 3 asks. End with whether a push to `staging` would publish the images.
