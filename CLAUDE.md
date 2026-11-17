# Glados

Glados is a manufacturing and production-planning system (catalogue items, demands,
procurement, production lots, scheduling, QA) integrated with a SolidWorks PDM vault. This repo
holds the Python 3.13 FastAPI backend (`backend/`, hexagonal, SQLAlchemy 2.0, async I/O) and the
Vue 3 + TypeScript frontend (`frontend/`, OpenVue 1, Pinia, Vite, Vitest). The SolidWorks add-in
(`glados-sw-addin`) is a separate repo and consumes the backend's `pat` API as an external client.

## Where the rules live

`docs/` is the single source of truth for conventions. This file and `.claude/skills/*` only
add AI-specific behaviour. The docs have two tiers: the guides in `docs/*.md` explain concepts
for humans, and `docs/reference/*.md` holds the exhaustive rules, checklists and edge cases.
Before changing code, read the guide section for the idea and the reference file for the rules
(`docs/reference/README.md` indexes every file):

| Topic | Guide | Reference |
| ----- | ----- | --------- |
| Architecture, bounded contexts, layers, wiring, import contracts | `docs/CONTRIBUTING.md` section 1 | `module-boundaries.md` |
| Recipes: endpoint, field, domain error, feature module, admin tab, PDF report | `docs/CONTRIBUTING.md` section 2 | `recipes.md` |
| Backend conventions: use cases, permissions, PATs, DTOs and schemas, quantities, logging | `docs/CONTRIBUTING.md` sections 3 to 3.3 | `backend-conventions.md` |
| Persistence, soft delete, events, the outbox and the unit of work commit model | `docs/CONTRIBUTING.md` sections 3.4 to 3.6 | `persistence.md` |
| Lifecycle reconciler protocol | `docs/CONTRIBUTING.md` section 3.7 | `lifecycle.md` |
| Every lifecycle as a diagram, generated from the code | `docs/LIFECYCLES.md` | |
| Frontend conventions, i18n and "Du" | `docs/CONTRIBUTING.md` sections 4 and 5 | `frontend-conventions.md` |
| The Glados look | `docs/CONTRIBUTING.md` section 4.1 | `design-look.md` |
| Handbook pages | `docs/CONTRIBUTING.md` section 6 | `handbook-pages.md` |
| Testing | `docs/CONTRIBUTING.md` section 7, `docs/DEVELOPMENT.md` section 9 | `testing.md`, `development-testing.md` (incl. Redis db 15) |
| Domain glossary | `docs/CONTRIBUTING.md` section 10 | `domain-rules.md` |
| Scheduling and Auto-Plan | `docs/CONTRIBUTING.md` section 11 | `scheduling.md` |
| Local setup, env, dev server, OpenAPI snapshot export | `docs/DEVELOPMENT.md` | `development-environment.md` |
| Migrations (running and writing) | `docs/DEVELOPMENT.md` section 6 | `development-migrations.md` |
| Datetime rule | `docs/DEVELOPMENT.md` section 8 | `development-datetime.md` |
| Async rules | `docs/DEVELOPMENT.md` section 10 | `development-async.md` |
| PDM/web field ownership, read before touching item code | `docs/FIELD_OWNERSHIP.md` | `field-ownership.md` |
| SolidWorks PDM integration end to end | `docs/PDM_INTEGRATION.md` | `pdm-*.md` |
| Time tracking through the time tracking service, incl. its contract, security and threat model | `docs/TIME_TRACKING.md` | `time-tracking-*.md` |
| Terminals and infoscreens: device sign-in, keys, approval, feed, live, threat model | `docs/TERMINAL_INTEGRATION.md` | `terminal-*.md` |
| AI agents through MCP: tokens, tools, drafts, redaction, call log, threat model | `docs/MCP_INTEGRATION.md` | `mcp-*.md` |
| Stock service settings and its contract | `docs/STOCK_SERVICE.md` | `stock-service.md` |
| EPLAN Data Portal and the spreadsheet import settings | `docs/EPLAN_DATA_PORTAL_INTEGRATION.md` | `eplan-data-portal.md` |
| Branching, release PRs, versioning, `pat` snapshot gate | `docs/RELEASING.md` | `releasing-ci.md`, `releasing-github-setup.md` |
| Why the code is shaped this way | `docs/adr/` | |
| Ops: install, operations, infrastructure | `docs/INSTALLATION.md`, `docs/OPERATIONS.md`, `docs/INFRASTRUCTURE.md` | `installation-*.md`, `operations-*.md` |

When a rule you need is missing from `docs/`, add it there, not here: a concept to the guide,
a rule to the reference file, never the same fact to both.

## Commands and what to run unprompted

Backend (from `backend/`):
- Tests: run ONLY the tests written or touched this session, targeted:
  `poetry run pytest tests/path/test_x.py -q` (or `-k <name>`), just enough to verify the
  feature. Never run the full suite (`poetry run pytest tests -q`) or whole directories
  (`tests/unit -q`, `tests/integration -q`) on your own; the `/test` skill covers the whole
  codebase and quality gates when the user wants that. A full run, when asked for, is
  parallel: `make test` from the repo root (`docs/reference/development-testing.md`).
- Gates: `poetry run ruff check src tests scripts alembic`,
  `poetry run ruff format --check src tests scripts alembic`, `poetry run mypy src scripts`
  (strict), `poetry run lint-imports`.
- After changing a route or schema: `poetry run python scripts/export_openapi.py`, then
  `npm run generate:api-types` in `frontend/` (the `export-openapi` pre-commit hook does both).
- Dev server: `docker compose -f docker-compose.dev.yml --env-file .env.dev up postgres redis -d`
  (repo root), then `ENV_FILE=../.env.dev poetry run uvicorn src.bootstrap.main:app --reload` (:3000).
  Under VS Code debugpy the reloader often does not reload; check worker age first.
- Alembic: load the `migrations` skill before writing a migration. Never run `alembic upgrade`
  unprompted (see Don't); state the file path and revision slug instead. An authored but
  unapplied migration on disk is normal, not a bug to fix.

Frontend (from `frontend/`):
- `npm run test:unit:run -- <spec path>` for the specs you touched.
- Gates: `npm run type-check`, `npm run lint:check`, `npm run check:i18n`,
  `npm run check:api-types`. `npm run ci` runs type-check, lint:check, test:unit:run,
  check:i18n and check:api-types in sequence.

## Don't

1. Never add a "Co-Authored-By: Claude" (or any AI) trailer to commit messages, and never commit
   or push unprompted; wait for an explicit ask every time.
2. Never break the layer dependency rule (adapters → application → ports → domain, inward only),
   and never import SQLAlchemy/Pydantic/FastAPI in a module's `domain/` or in `src/shared_kernel/`.
3. Never apply database migrations to any database unprompted, never write one that assumes
   optional/vestige columns exist, and never point tests or dev scripts at a real database;
   tests use a throwaway SQLite file.
4. Never use plain `caplog` in unit tests; use `glados_caplog` (app logger has
   `propagate=False`, so `caplog` silently sees nothing).
5. Never reverse `data_source` CAD→WEB, reuse a part number, or hand-edit generated files
   (frontend `webSchema.ts`, OpenAPI snapshots, `docs/LIFECYCLES.md`).
6. Never change an existing test to make new code pass without flagging it first.
7. Always ask before driving a live browser test, even a read-only one, and always write German
   user-facing copy (mail templates and UI) in informal "Du", never "Sie".
8. Never run the full test suite or the whole quality-gate set unprompted; run only the
   session's own tests; `/test` exists for the full run.
9. Never reference plan-points or decision-points (e.g. `D13`, `WP-A4`) or `.playground/` in
   code comments or documentation: plans are local working artifacts; code and docs must stand
   alone.
10. Never write German in code, identifiers, comments, docstrings, log messages, or docs; the
    repo language is 100% English. German belongs only in locale/translation files (mail
    templates, frontend i18n).
11. Never run prettier in `frontend/`: no prettier config exists, so match single-quote /
    no-semicolon style by hand.
12. Never introduce Tailwind or any utility-CSS framework in the frontend; use scoped CSS or
    OpenVue.
13. Never use `@media (prefers-color-scheme: dark)` in Vue components; OpenVue CSS variables
    handle theming.
14. Before adding an admin-settings tab, mirror the conventions of the existing
    `AdminSettingsTab*.vue` siblings (`docs/reference/recipes.md` section 5).

## Writing style for comments and docs

Docstrings and comments (both halves) are precise and human readable, never padded out: normal
sentences with normal commas, no em dashes or dash-joined clauses, no bullet-style fragments.
Say what the thing does and why it exists, then stop. Full rule: `docs/CONTRIBUTING.md`
section 9.

## Workflow

- `.playground/` (gitignored) is the planning and decision-record hub: one folder per effort,
  `<topic>-<YYYY-MM-DD>/plan.md` with Goal, pinned Decisions (Dxx), Confirmations, Findings,
  Target behaviour, Implementation breakdown, Traceability.
- Pinned decisions (Dxx) in a plan are settled; do not relitigate them without a new, explicit
  reason from the user.
