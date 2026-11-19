---
name: migrations
description: Writing, changing or reviewing an Alembic migration in Glados. Load before creating any file under backend/alembic/versions, before running any alembic command, and whenever a model change needs a schema change.
---

# Writing a Glados migration

The rules live in `docs/reference/development-migrations.md` (read sections 1 to 4 in full first). This skill is the order to follow, because doing the right steps in the wrong order is what forces manual database repairs.

The history runs in one line from a single initial migration. Released migrations are immutable, since production databases have applied them, and every migration carries production data forward, so a database upgraded from any release ends up holding what a fresh install would. A migration upgrades every database with no manual step. Nobody edits `alembic_version` or stamps a revision.

## Hard rules

- Never run `alembic upgrade`, `downgrade` or `stamp` against any database, and never run a
  bare `alembic revision` (the empty template is the trap below).
- The dev backend applies every file in `alembic/versions/` on start and on every reload when
  `DEBUG=true`. An unfinished file is applied the moment anything under `backend/src` changes.
- Never edit, rename, re-id or delete a migration that is on `main`. Fix forward with a new one.
  A migration that exists only on the current branch is changed instead of followed by a second
  one, but only after the user has downgraded every database that applied it
  (`docs/reference/development-migrations.md` section 5). You never run that downgrade yourself.
- Never write a second migration on a branch that already has one without asking the user
  first and getting an explicit yes. Extending the existing one is the default.
- Never import from `src` in a migration. Use `sa.table()` / `sa.column()` stubs and SQL.

## Steps

1. **Change the models first** (and register a new model in
   `src/modules/platform/adapters/outbound/persistence/alembic_imports.py`). Then load the `database` skill's
   model rules if you have not.
2. **Find the head:** `cd backend && poetry run alembic heads`. Exactly one is expected; if
   there are two, stop and tell the user. Then check whether the branch already has its own
   migration: `git diff --name-only main...HEAD -- alembic/versions` plus untracked files in
   `alembic/versions/`. If it has one, the new schema change goes into that file (section 5 of
   the reference) unless the user approves a second one: before editing it, ask the user to run
   `poetry run alembic downgrade <its down_revision>` on the dev database, and wait for that.
3. **See the diff without writing a file:** `poetry run alembic check` lists the operations
   autogenerate would emit (it reads the dev database, it does not change it).
4. **Write the whole file in one Write call**, not a template filled in later:
   - revision id: `python3 -c "import uuid; print(uuid.uuid4().hex[:12])"`;
   - `down_revision` = the head from step 2;
   - file name `alembic/versions/YYYY_MM_DD_HHMM-<rev>_<slug>.py`;
   - the header and imports `alembic/script.py.mako` renders, and a docstring saying what
     the revision changes, why, and what downgrade does.
   `alembic revision --autogenerate` is allowed only if you review and finish its draft
   before touching `backend/src` again; prefer hand-writing.
5. **Apply the checklist of section 3.2 line by line:** guard every create and drop with an inspection (in upgrade and downgrade), `server_default` on new NOT NULL columns, `op.batch_alter_table` for what SQLite cannot alter in place, both partial-index predicates, explicit constraint names, `HAND_MAINTAINED_OBJECTS` for raw DDL, and a working downgrade.
6. **Data steps:** idempotent (a second run changes nothing), tolerant of unexpected rows (skip or default, never raise on data), batched for large tables. A change to the shape or meaning of stored data converts the existing rows in the same revision, and a new key in a stored JSON settings value is written with its default into every stored row. No seed data: singletons and slots the code needs belong in `InitDatabase`.
7. **Check it:**
   - `poetry run pytest tests/integration/test_alembic_migrations.py tests/unit/test_schema_indexes.py -q` (whole chain to head on SQLite, one head, indexed foreign keys);
   - the tests of the models and repositories you changed;
   - `poetry run ruff check alembic` and `poetry run ruff format --check alembic`;
   - CI runs `tests/integration/test_migrations_postgres.py` on an empty Postgres; run it
     locally only with `GLADOS_TEST_PG_URL` pointing at an empty throwaway database the user
     provides, never the dev one.
   `alembic upgrade --sql` cannot render the inspection guards, so do not use it as a check.
8. **Hand over:** name the file path and revision id, say it is not applied, and say that a
   running dev backend applies it on its next reload. Add that before switching the dev
   database back to `main` or another branch, the user downgrades it on this branch to the
   migration's `down_revision`, or the backend there refuses to start.

## If a database was stamped without its DDL

Tell the user; do not fix it yourself. The repair they run, from `backend/`, is
`poetry run alembic downgrade <revision before it>` and then `poetry run alembic upgrade head`,
after making sure the migration body is complete.
