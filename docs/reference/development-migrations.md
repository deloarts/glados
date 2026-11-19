# migrations

The rules for writing and checking an Alembic migration in the backend. [DEVELOPMENT.md section 6](../DEVELOPMENT.md#6-database-migrations) explains when migrations run and gives the everyday commands; this file holds everything a migration has to get exactly right. All paths are relative to `backend/`.

- [migrations](#migrations)
  - [1 the chain](#1-the-chain)
  - [2 what forces a manual repair](#2-what-forces-a-manual-repair)
  - [3 writing a migration](#3-writing-a-migration)
    - [3.1 creating the file](#31-creating-the-file)
    - [3.2 schema rules](#32-schema-rules)
    - [3.3 data steps](#33-data-steps)
  - [4 checking a migration](#4-checking-a-migration)
  - [5 migrations on a branch](#5-migrations-on-a-branch)

## 1 the chain

- The history starts at a single initial migration, generated from the models, and runs in one line from there. Its `downgrade()` raises, since there is no earlier schema to return to.
- A new migration builds on the single head, which `poetry run alembic heads` shows and autogenerate takes as the new `down_revision`. CI fails on multiple heads.
- A database whose `alembic_version` is not part of this history cannot be upgraded.
- Released migrations are immutable. Once a release has shipped a migration, production databases have applied it, so it is never edited, renamed, given a new revision id or deleted, and the chain is never squashed.
- Every migration carries production data forward. A migration that changes the shape or meaning of stored data converts the existing rows in the same revision, so a database upgraded from any release ends up with the same data a fresh install would hold.
- Release images run `alembic upgrade head` from `docker/entrypoint.sh` on every start, so a broken migration is a broken deployment, not just a failing dev command.
- Migrations are applied by whoever runs the target database. Do not apply a migration to a shared or production database as part of writing it; an authored but unapplied migration on disk is normal.

## 2 what forces a manual repair

A migration must never need a person to repair the database afterwards. Nobody edits `alembic_version`, stamps a revision or reruns DDL by hand, and a migration that would need that is a bug in the migration. Each cause below comes with the rule that prevents it.

| Cause | Rule |
| ----- | ---- |
| A reloading dev backend applies an empty `alembic revision` template and marks the revision as done although no DDL ran. | Write the complete file before anything under `backend/src` changes, or write it by hand in one go ([section 3.1](#31-creating-the-file)). |
| A migration is edited, renamed, given a new revision id or deleted after a database applied it, which leaves that database on a revision the scripts no longer describe. | Once the migration is on `main`, fix forward with a new migration. While it is still on its branch, downgrade every database that applied it before changing it ([section 5](#5-migrations-on-a-branch)). |
| Another branch also added a migration, and the two heads stop `alembic upgrade head`. | Before committing, point the new migration's `down_revision` at the current head (`poetry run alembic heads`) instead of adding a merge migration. |
| DDL assumes the database matches the models and fails on a database that was repaired by hand or is a revision behind. | Guard every create and drop with an inspection ([section 3.2](#32-schema-rules)). |
| A data step fails on an unexpected row and stops the upgrade half way. | Make data steps idempotent and tolerant ([section 3.3](#33-data-steps)). |
| Code imported from `src` changes after the migration was written, so the migration stops doing what it did. | Never import from `src` in a migration ([section 3.3](#33-data-steps)). |

## 3 writing a migration

### 3.1 creating the file

- Change the models first, then write the migration. `poetry run alembic check` lists the model changes no migration covers yet, without writing a file.
- Either write the file by hand in one go, with a 12-character hex revision id, `down_revision` set to the current head and the file name below, or generate a draft with `poetry run alembic revision --autogenerate -m "add supplier rating"`.
- A reloading dev backend applies a draft the moment anything under `backend/src` changes. Finish and review the draft before touching `src` again, or stop the dev backend while you write it.
- The file name is `alembic/versions/YYYY_MM_DD_HHMM-<rev>_<slug>.py`, with a hyphen after the time and an underscore before the slug, for example `2026_11_20_0915-<rev>_add_supplier_rating.py`.
- `alembic/script.py.mako` renders the draft in the shape every migration has: the header docstring, the revision annotations, and imports sorted the way ruff sorts them. Write what the revision changes and why, and what downgrade does, into the docstring below the header.
- Read and fix the draft before committing it, against the rules in [section 3.2](#32-schema-rules) and [section 3.3](#33-data-steps).
- A new model is registered in `src/modules/platform/adapters/outbound/persistence/alembic_imports.py`, because autogenerate only sees models imported there.

### 3.2 schema rules

- **Never assume an optional column, index or table exists.** Inspect first (`sa.inspect(op.get_bind())`) or use `IF EXISTS`, in both `upgrade` and `downgrade`. A migration that assumes one crash-loops every deployment whose database lacks it, for example one that was repaired by hand.
- **A new `NOT NULL` column needs a `server_default`**, so existing rows get a value. Decide whether a later migration should drop the default once every row holds a real value.
- **Both dialects.** Postgres runs in production and SQLite runs the tests, so every model feature must work on both.
- **No global batch mode.** `alembic/env.py` deliberately does not set a global `render_as_batch=True`, because Postgres alters tables natively, and it is not added back. The individual operations SQLite cannot do in place (dropping or altering columns, some constraint changes) are wrapped in `op.batch_alter_table(...)`.
- **Partial unique indexes carry both clauses.** Soft-deleted rows must not block a new live row, so uniqueness is a partial index with a Postgres and a SQLite predicate. With only one, the index silently constrains nothing on the other dialect:

  ```python
  Index(
      "uq_supplier_vat_id_active",
      "vat_id",
      unique=True,
      postgresql_where=text("archived IS false"),
      sqlite_where=text("archived = 0"),
  )
  ```

- **Every constraint is named explicitly** (`name="fk_supplier_creator_id"`), because there is no global naming convention.
- **Server defaults** are compared by the custom `compare_server_default` in `src/modules/platform/adapters/outbound/persistence/autogenerate_filters.py`. Still check that default changes came out as intended.
- **Hand-maintained objects.** The trigram GIN indexes behind global search and the log filters are created with raw `op.execute()` and are not on any model. They are listed in `HAND_MAINTAINED_OBJECTS` in `autogenerate_filters.py` so autogenerate ignores them. Any new hand-written DDL object is added there. Do not try to make autogenerate pick them up: search uses ILIKE plus trigram precisely so that the SQLite tests keep working without trigram support.
- **Try SQLite when unsure.** If you are not sure an operation works on SQLite, run it there once instead of assuming Postgres DDL carries over.
- **Models must stand alone.** Tests build the schema with `Base.metadata.create_all()`, not with Alembic, so every column, default and constraint a test relies on must be declared on the model too.

### 3.3 data steps

- A data step is idempotent and tolerant. It skips or defaults what it cannot convert, and the migration's docstring says so.
- A migration never imports from `src`. It uses `sa.table()` and `sa.column()` stubs and raw SQL instead.
- A revision never loads another revision's module to run its code.
- A new key in a stored JSON settings value, such as a PDM variable map or the made-item revision policy, is added by a data migration that writes the key's default into every stored row. The code reads a stored settings value as complete and does not fill in missing keys at read time, so a row without the key is a migration that was never written. `InitDatabase` seeds the complete defaults on a fresh install, so the migration only has to carry the rows that already exist.
- Seed data does not go into migrations. The singletons and slots the code needs are ensured by `InitDatabase` at startup, and recommended content is imported by the admin from the root `templates/` folder.

## 4 checking a migration

- `poetry run pytest tests/integration/test_alembic_migrations.py -q` applies the whole chain to head on SQLite and checks that the history has a single head.
- CI also runs `tests/integration/test_migrations_postgres.py` against an empty Postgres, which upgrades the chain and compares the result with the models.
- `alembic upgrade --sql` cannot render migrations that inspect the database first, so it is no substitute for these tests.

## 5 migrations on a branch

A migration is fixed once it reaches `main`, because everything on `main` ships with the next release. Until then it lives on its branch, and the only databases that applied it are the developer's dev database and any test server the branch was deployed to. The rules below keep those databases repairable without stamping and keep the history on `main` at usually one revision per pull request.

- **Prefer one migration per branch.** A further schema change on the same branch goes into the branch's existing migration by default. A second migration is the exception and needs the explicit approval of the branch owner, for example when the first one is already applied on a test server that should not be reset; the pull request then says why there are two.
- **Changing the branch's migration.** Before editing, renaming or deleting it, downgrade every database that applied it to the revision it builds on, by running `poetry run alembic downgrade <down_revision>` on the branch. Then change the file and let the dev backend apply it again. Changing it without the downgrade is the repair case of [section 2](#2-what-forces-a-manual-repair).
- **Two migrations on one branch without that approval.** Downgrade to the revision the first of them builds on, move the operations of the second into the first, delete the second, and check that `poetry run alembic heads` shows a single head.
- **Before the pull request.** If `main` gained a migration since the branch started, point the branch migration's `down_revision` at the new head of `main` ([section 2](#2-what-forces-a-manual-repair)). Downgrade the dev database before changing `down_revision`, since that changes the chain the database sits on.
- **Leaving the branch.** A dev database that applied the branch's migration is ahead of every branch without it, and the backend refuses to start there. Before switching to `main` or another branch, downgrade the dev database on this branch to the revision its migration builds on. The downgrade keeps the rest of the dev data and runs the migration's `downgrade()` against real rows, which tests it on every switch. If the switch already happened and the backend refuses to start, check the branch out again, downgrade there, and switch back.
- **Test servers.** A test server that ran the branch keeps the migration in its database, so switching it to another line of work needs a restore from backup or a reset ([RELEASING.md section 4.4](../RELEASING.md#44-caveats)). Deploy a branch with a migration there only once the migration is final.
