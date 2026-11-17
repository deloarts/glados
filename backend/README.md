# glados backend

Python 3.13 / FastAPI backend for [GLADOS](../README.md) - SQLAlchemy 2.0,
Alembic, PostgreSQL, Redis.

```bash
cd backend
poetry install
poetry run pytest
poetry run python scripts/export_openapi.py   # re-export the OpenAPI snapshots
```

See the [root README](../README.md) for the full-stack quick start, and
[docs/](../docs/) for development, installation, operations, infrastructure
and release documentation.
