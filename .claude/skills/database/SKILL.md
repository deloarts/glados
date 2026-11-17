---
name: database
description: Working with the Glados database: schema changes, new SQLAlchemy models, Alembic migrations, SQLite test compatibility, and event/commit ordering. Load before touching anything under adapters/outbound/persistence/ or writing a migration.
---

# Glados database conventions

Every database rule is documented in `docs/`. Read the parts that apply before writing code:

- Writing migrations: the `migrations` skill and `docs/reference/development-migrations.md`.
- Models, repositories, load options and `populate_existing`, session usage, advisory locks,
  stored statuses, `init_db.py` seeding: `docs/reference/persistence.md` section 1.
- Soft delete (`archived`, `include_archived`, archive/restore routes, live-row uniqueness):
  `docs/reference/persistence.md` section 2.
- Event/commit ordering and the unit of work commit model: `docs/reference/persistence.md`
  sections 1.7 and 3.
- Test database (SQLite file, `create_all`, truncation, Redis db 15):
  `docs/reference/development-testing.md`.

## Migrations

Load the `migrations` skill before creating or changing anything under `backend/alembic/`. It
holds the order of steps, the never-apply rule and the checks. The dev backend applies every
file in `alembic/versions/` on start and reload, so an authored migration does not stay
unapplied on dev for long; it stays unapplied on staging until the next deployment.

## What to run

Run only the tests that cover the change, targeted.
