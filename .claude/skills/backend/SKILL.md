---
name: backend
description: Implementing a backend feature, API endpoint, or use case in Glados. Load when adding or changing anything under a module's application, adapters/inbound/api or domain folder (src/modules/<module>/) in service of a new operation.
---

# Glados backend conventions

Every backend rule is documented in `docs/reference/` (the guides in `docs/` explain the
concepts). Read the parts that apply before writing code:

- New API operation: `docs/reference/recipes.md` section 1 (schema, DTO, use case, domain, port,
  mapper, deps factory, endpoint, OpenAPI snapshots, frontend types).
- New field: `docs/reference/recipes.md` section 2 (full fan-out checklist).
- New domain error: `docs/reference/recipes.md` section 3 (define it in the raising module's
  `domain/errors.py` and inherit a semantic base from Platform's `exceptions.py`; never rename a
  shipped error, its class name is the response `code`).
- Use cases, auth, permissions, maintenance mode, PAT scopes, DTO vs schema, logging:
  `docs/reference/backend-conventions.md`. Persistence, soft delete, events and the unit of work
  commit model: `docs/reference/persistence.md`.
- Module boundaries and import contracts: `docs/reference/module-boundaries.md`.
- Lifecycle statuses (facts, intents, the reconciler protocol): `docs/reference/lifecycle.md`.
- Scheduling, the forward walk and Auto-Plan: `docs/reference/scheduling.md`.
- Async rules (sync domain, async ports, offloading with `anyio.to_thread`, no `asyncio.gather`
  on one session, load options): `docs/reference/development-async.md`.
- Tests (fakes, `glados_caplog`, `auth_client`, Redis db 15, SQLite): `docs/reference/testing.md`
  and `docs/reference/development-testing.md`.
- Item fields: `docs/FIELD_OWNERSHIP.md` and `docs/reference/field-ownership.md` before touching
  made, bought or source item code.

## What to run

From `backend/`, before calling a change done:

1. `poetry run ruff check src tests scripts alembic`
2. `poetry run ruff format --check src tests scripts alembic`
3. `poetry run mypy src scripts`
4. `poetry run lint-imports`
5. `poetry run pytest <the test files you wrote or touched> -q`, never the full suite or whole
   directories unprompted.

If a route or schema changed, also run `poetry run python scripts/export_openapi.py` and
`npm run generate:api-types` in `frontend/`, then `poetry run python scripts/check_openapi.py`.
Tell the user if the `pat` snapshot changed, since that needs a minor version bump.

If an existing test looks wrong given your change, say so and ask before touching it.
