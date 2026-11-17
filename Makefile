# Thin wrappers over the commands documented in docs/DEVELOPMENT.md, so the
# common loops are one command each. Every target runs exactly what the docs
# describe; read a recipe to see the underlying command.
#
#   make setup         install backend and frontend dependencies and the git hooks
#   make infra         start Postgres and Redis for the host dev loop
#   make migrate       apply Alembic migrations to the dev database (.env.dev)
#   make dev-backend   run the backend with reload on :3000
#   make dev-frontend  run the Vite dev server on :5173
#   make test-fast     backend unit + smoke integration tests, frontend unit tests
#   make test          the full backend suite, frontend unit tests
#   make test-durations  record backend test durations for the CI shard split
#   make gates         lint, format, type and contract checks of both halves
#   make size-report   list backend functions over 100 lines (report only)

POETRY ?= poetry
NPM ?= npm
COMPOSE_DEV = docker compose -f docker-compose.dev.yml --env-file .env.dev
INFRA_SERVICES ?= postgres redis

.PHONY: help setup infra migrate dev-backend dev-frontend test-fast test test-durations \
	gates gates-backend gates-frontend size-report

help:
	@sed -n 's/^#   //p' Makefile

setup:
	test -f .env.dev || cp .env.dev.example .env.dev
	cd backend && $(POETRY) install
	cd backend && $(POETRY) run pre-commit install
	cd frontend && $(NPM) ci

infra:
	$(COMPOSE_DEV) up -d $(INFRA_SERVICES)

migrate:
	cd backend && ENV_FILE=../.env.dev $(POETRY) run alembic upgrade head

dev-backend:
	cd backend && ENV_FILE=../.env.dev $(POETRY) run uvicorn src.bootstrap.main:app --reload --port 3000

dev-frontend:
	cd frontend && $(NPM) run dev

# The backend tests need Redis on localhost (database 15), `make infra`
# provides it. The database itself is a throwaway SQLite file.
test-fast:
	cd backend && $(POETRY) run pytest tests/unit -q -n auto --maxprocesses 15 -m "not benchmark"
	cd backend && $(POETRY) run pytest tests/integration -m smoke -q
	cd frontend && $(NPM) run test:unit:run

# The backend suite runs on up to 15 xdist workers, one Redis database each;
# the wall-clock benchmark and the Postgres race tests run in one process.
test:
	cd backend && $(POETRY) run pytest tests -q -n auto --maxprocesses 15 -m "not benchmark" --ignore tests/pg
	cd backend && $(POETRY) run pytest tests -q -m benchmark
	cd backend && $(POETRY) run pytest tests/pg -q
	cd frontend && $(NPM) run test:unit:run

# Records how long each backend test takes, the way a CI shard runs it, into
# backend/.test_durations, which pytest-split balances the CI shards by.
# Rerun and commit the file when the shards' run times drift apart.
test-durations:
	cd backend && COVERAGE_FILE="$$(mktemp -d)/.coverage" $(POETRY) run pytest tests --ignore=tests/pg -q -n auto --maxprocesses 8 --cov=src --cov-report= --cov-fail-under=0 --hypothesis-profile ci --store-durations --clean-durations

gates: gates-backend gates-frontend

gates-backend:
	cd backend && $(POETRY) run ruff check src tests scripts alembic
	cd backend && $(POETRY) run ruff format --check src tests scripts alembic
	cd backend && $(POETRY) run mypy src scripts
	cd backend && $(POETRY) run lint-imports
	cd backend && $(POETRY) run python scripts/check_openapi.py
	python3 scripts/check_plan_refs.py

gates-frontend:
	cd frontend && $(NPM) run type-check
	cd frontend && $(NPM) run lint:check
	cd frontend && $(NPM) run check:i18n
	cd frontend && $(NPM) run check:api-types

size-report:
	cd backend && $(POETRY) run python scripts/check_function_length.py
