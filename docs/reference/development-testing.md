# test conventions

The rules for running and writing backend tests: how the suite is run and isolated, the shared fixtures and fakes, the property tests, and the Postgres race tests. [DEVELOPMENT.md section 9](../DEVELOPMENT.md#9-test-conventions) gives the everyday commands. All paths are relative to `backend/`.

- [test conventions](#test-conventions)
  - [1 running tests](#1-running-tests)
    - [1.1 the full run](#11-the-full-run)
    - [1.2 the fast loop and test selection](#12-the-fast-loop-and-test-selection)
    - [1.3 in ci](#13-in-ci)
  - [2 isolation](#2-isolation)
  - [3 writing tests](#3-writing-tests)
    - [3.1 log capture](#31-log-capture)
    - [3.2 test data](#32-test-data)
    - [3.3 async tests](#33-async-tests)
    - [3.4 shared fakes](#34-shared-fakes)
    - [3.5 the fake contract test](#35-the-fake-contract-test)
    - [3.6 must-not-raise tests](#36-must-not-raise-tests)
  - [4 property tests and hypothesis profiles](#4-property-tests-and-hypothesis-profiles)
  - [5 postgres race tests](#5-postgres-race-tests)
    - [5.1 the throwaway database](#51-the-throwaway-database)
    - [5.2 how a race test works](#52-how-a-race-test-works)
    - [5.3 race coverage of reconciler use cases](#53-race-coverage-of-reconciler-use-cases)
    - [5.4 what the version column catches](#54-what-the-version-column-catches)
    - [5.5 the backup and restore drill](#55-the-backup-and-restore-drill)

## 1 running tests

### 1.1 the full run

`make test` at the repository root runs the backend suite in parallel with pytest-xdist, in three steps:

```bash
poetry run pytest tests -q -n auto --maxprocesses 15 -m "not benchmark" --ignore tests/pg
poetry run pytest tests -q -m benchmark             # wall-clock guard, alone
poetry run pytest tests/pg -q                       # race tests, one process
```

- Each xdist worker gets its own throwaway SQLite file and its own Redis database, counting down from 15, which is why a run takes at most 15 workers.
- The benchmark measures wall-clock time, so it runs without other workers competing for the CPU.
- The race tests share one Postgres database and make their own concurrency, so they refuse to run under `-n`.

### 1.2 the fast loop and test selection

- `make test-fast` at the repository root runs the backend unit tests, the integration tests marked `smoke` and the frontend unit tests.
- A new integration test is marked `@pytest.mark.smoke` only if it is fast and covers a main path no other smoke test does.
- `scripts/select_tests.py` prints the backend test files a change can reach: the tests that import a changed module or a module that depends on it, the changed test files and the boundary guards. A change to the shared kernel, the composition root, the read tier, a conftest or the dependencies selects the whole suite. Run it as `poetry run pytest $(poetry run python scripts/select_tests.py) -q -n auto`.

### 1.3 in ci

- CI runs the full suite on every pull request, split into four parallel shards by pytest-split, and enforces the coverage threshold on the combined result.
- CI runs the race tests in their own job, `backend-pg-races`, split into four parallel shards that each get an empty Postgres service. The backend test shards leave all of `tests/pg` out. Which branches run them is in [releasing-ci.md section 1](releasing-ci.md#1-the-ci-workflow), and `nightly.yml` runs all of `tests/pg` on `main` every night ([releasing-ci.md section 1.4](releasing-ci.md#14-the-nightly-workflow)).
- The backup and restore drill ([section 5.5](#55-the-backup-and-restore-drill)) runs in the first backend test shard on every run, in its own step, and the race test shards leave it out.
- CI passes `--hypothesis-profile ci` ([section 4](#4-property-tests-and-hypothesis-profiles)).

## 2 isolation

- The tests need no Redis server, and CI runs them without one. The integration suite replaces the event bus, the replay guard and the login attempt tracker with in-process fakes, and the unit tests of the Redis-backed adapters use in-memory fake clients.
- `tests/conftest.py` still points `REDIS__URL` at database 15 on `localhost:6379` (14, 13 and so on for further xdist workers), never 0, so a write that slips past those fakes can never reach a dev backend consuming db 0.
- No Postgres is needed either, apart from the opt-in race tests ([section 5](#5-postgres-race-tests)).
- `tests/conftest.py` points `DATABASE__URL` at a file in a temporary directory. It is a file rather than an in-memory database because the suite needs several connections to see the same data.
- `tests/integration/conftest.py` asserts on the resolved URL before it creates or truncates anything, so the suite can never wipe a real database.
- Alembic does not run in tests. The schema comes from `Base.metadata.create_all()`, and tables are truncated between tests.
- If `ENV_FILE` is set, the test configuration backs off, so unset it before running tests.

## 3 writing tests

### 3.1 log capture

The app logger has `propagate=False`, so plain `caplog` sees nothing. Use the `glados_caplog` fixture instead; it is defined in `tests/conftest.py`, so unit and integration tests can both use it.

### 3.2 test data

`tests/factories.py` builds domain entities for unit and integration tests alike. Its `make_user(**overrides)` returns a valid `User` whose password hash is computed once per session, so new tests use it, or a thin local wrapper around it, instead of writing their own copy.

### 3.3 async tests

- The suite runs on pytest-asyncio with `asyncio_mode = "auto"`, so a plain `async def test_...` needs no marker.
- Unit tests await the use case they exercise, and every fake implements the async port methods it stands in for as `async def`.
- Integration tests send requests through `httpx.AsyncClient` over `ASGITransport` (the `client` and `auth_client` fixtures), which never runs the app's lifespan.
- Integration tests arrange or assert database state through the `db` fixture, an `AsyncSession` on the app's async engine.
- Schema creation, seeding and per-test truncation run on a separate sync engine against the same throwaway SQLite file, so they never touch the event loop.

### 3.4 shared fakes

- `FakeUnitOfWork` and `FakeEventBus` live in `tests/unit/fakes.py`, with fixtures in `tests/unit/conftest.py`. A unit test that needs either uses the shared version (the `fake_uow` and `fake_event_bus` fixtures, or the classes imported directly) rather than a local copy.
- A local copy is replaced when its file is edited for another reason. A passing test is not a defect, so no standalone change is warranted.
- Repository-shaped fakes stay in their test package's `fakes.py` or in the test file. They carry per-test seed data and are not interchangeable.

### 3.5 the fake contract test

`tests/unit/test_fakes_contract.py` checks every class in a `tests/**/fakes.py` module against the port it stands in for.

- It fails when a class in such a module has no entry in its `CONTRACTS` list. Each entry names the fake and its port explicitly.
- For every port method the fake defines, the fake must be async exactly when the port is, take the port's positional parameters under the same names and in the same order, and accept its keyword-only parameters.
- A fake may add parameters of its own only with a default, and it must keep any default the port gives.
- A fake that defines only the methods its tests reach is marked `partial`. Any other fake must define every port method.
- A public method the port does not declare fails the check unless the entry lists it under `helpers` as a test-only method, so a method the port has dropped is deleted from the fake rather than left behind.
- When you change a port signature, update the fakes the test names, and when you add a fake to a `fakes.py` module, add its entry.
- Fakes defined inside a single test file are not covered, so keep their signatures in step with the port by hand.

### 3.6 must-not-raise tests

A test whose only assertion is that a function call did not raise is acceptable only when it carries a comment documenting that intent and still asserts on the return value or resulting state whenever the function under test returns or mutates anything. A bare call is permitted only for a `-> None` validator. A test that falls short of this is upgraded when its file is edited for another reason, following the same rule as the shared fakes.

## 4 property tests and hypothesis profiles

- The lifecycle property tests and rule-based models run on Hypothesis profiles registered in `tests/conftest.py`. They are the cross-aggregate model and the demand model in `tests/unit/lifecycle/`, and the order, lot and production order models beside those aggregates' tests.
- `dev`, loaded by default, runs 100 random examples per test and keeps failing examples in the gitignored `.hypothesis/` database, so a local rerun replays them.
- CI passes `--hypothesis-profile ci`: 400 examples, derandomized so every run checks the same ones, without a deadline and without the example database.
- A rule-based model takes the profile's count through `model_settings` in `tests/unit/lifecycle/_profiles.py`. The two expensive models, the lot model and the cross-aggregate model, take a weighted share of it, so the property suite stays within a few minutes in CI.
- A failure prints the steps that reproduce it and, under `ci`, a `@reproduce_failure` blob. Run the file locally with `--hypothesis-profile ci` to see the same examples.

## 5 postgres race tests

Row locks, advisory locks and the version columns only behave as in production on Postgres, so the tests that race two requests against each other live in `tests/pg/` and run there. So do the tests of SQL that only Postgres runs, such as the global search's fuzzy tier, which calls `pg_trgm`'s `similarity()` where the SQLite suite has a Python stand-in. The commands to run them are in [DEVELOPMENT.md section 9](../DEVELOPMENT.md#9-test-conventions).

### 5.1 the throwaway database

- The tests are skipped unless `GLADOS_TEST_PG_URL` names a database.
- That database must be an empty throwaway one. The session creates every table from the models, refuses to start when the `public` schema already holds a table, empties every table after each test and drops them all at the end.
- The schema comes from the models, not the migrations, so a test that needs an extension a migration creates, such as `pg_trgm`, creates it itself with `CREATE EXTENSION IF NOT EXISTS`. Dropping the tables leaves the extension in place.
- The test engines carry the application's server-side timeouts and translate a unique violation into the port's `ConstraintViolationError`, as the application's engine does, so the numbering retry behaves as in production.
- Never point `GLADOS_TEST_PG_URL` at the development database.

### 5.2 how a race test works

- Each test gives the two requests their own engines and sessions and stops the first one inside the use case at a chosen point, usually once it holds its locks.
- Where the second one must wait for those locks, the test shows from `pg_stat_activity` that it does.
- Where the race is about what the first one read before its locks, the second one commits meanwhile.
- The test then asserts the committed state.

### 5.3 race coverage of reconciler use cases

- Every use case that runs the lifecycle reconciler needs a race test or an exemption in `tests/unit/test_race_test_coverage.py` that says why it needs none, usually because it takes the same locks through the same lock plan as a writer whose race is tested.
- That unit test counts a use case as covered when a `tests/pg` module builds it, or a subclass of it, through its dependency getter, so a new writer fails it until it has one or the other.

### 5.4 what the version column catches

- The lifecycle tables (lots, production orders, orders, order lines and the three demand tables) carry a `version` column that the mapper checks and increments on every ORM update and delete.
- A write that loses the check raises `StaleDataError`, which the API answers with 409 and the code `ConcurrentModificationError`.
- The check compares with the version the session holds for the row, and a repository save loads the row again when the session no longer holds it. It therefore catches a write whose session still holds an older copy, typically an update that waited for another transaction's row lock, but not a save from an entity that was read earlier while the session has let the row go.
- A use case that checks before it writes therefore takes its row locks through the request's lock plan before it reads, and the version check is the backstop behind those locks.
- A writer that draws a queue place takes the queue's lock before any row lock. An edit of a production order's pin or planned window does so too, so it waits for a running Auto-Plan and is applied on top of its result.

### 5.5 the backup and restore drill

- `tests/pg/test_backup_restore_drill.py` seeds a database, backs it up with the app's backup job, changes the data, restores the archive with the restore command and compares every table's row count with the counts at backup time. It covers encrypted and plain archives, a running database with an open connection and a lost one, and shows that a truncated archive, the wrong key, SQL that fails halfway and an archive without `alembic_version` all leave the current database untouched. It also runs the pre-migration dump and shows that a second migration waits for the migration lock.
- Each test creates its own scratch database `glados_drill_<random>` on the server `GLADOS_TEST_PG_URL` names and drops it at the end, together with every database the restore derived from its name. The shared throwaway database is never renamed, so the drill needs a user that may create databases, as the CI service's superuser can.
- The drill needs `pg_dump` and `psql` on the `PATH` and is skipped without them. The CI step prints both versions first, so a missing tool fails the step instead of skipping the drill.
