"""
Alembic migration environment. It reads DATABASE_URL from Settings and imports every ORM model
through alembic_imports.py. It does not use render_as_batch, since that exists only for SQLite
and Postgres supports ALTER TABLE natively.

It passes compare_server_default=compare_server_default (not a bare True), so Alembic detects
server-side default changes on every column except those of type `JSON`. Postgres defines no `=`
operator for plain `json`, so the generic comparison probe (`SELECT '[]'::json = '[]'`) would
raise UndefinedFunction and crash `alembic check` and `--autogenerate`. The callback skips such
columns by type, so a new JSON column needs no registration, but a change to its server default
is never detected and has to be written into a migration by hand.

It also passes include_object=include_object to exclude the hand-maintained-in-SQL objects:
`ix_bought_item_trgm_search` (a GIN trigram expression index) plus the single-column GIN
trigram indexes behind global search and the log filters, all created via raw `op.execute()`
in migrations. Declaring any of these as a normal SQLAlchemy Index
would risk a byte-for-byte mismatch against Postgres's normalised rendering of the expression, which
would make `alembic check` flag a spurious add+remove pair forever instead of converging, so they
are named explicitly via `autogenerate_filters.HAND_MAINTAINED_OBJECTS` rather than ignored as a
blanket exclusion: a real new drift on the same table still surfaces. Both callbacks and the
exclusion list live in
src/modules/platform/adapters/outbound/persistence/autogenerate_filters.py, not here, so
tests/integration/test_migrations_postgres.py can reuse them without importing this module's
side effects.

Every online run takes a transaction-scoped Postgres advisory lock
(AdvisoryLockKey.MIGRATION) before it reads the current revision, and holds
it until the migration transaction commits. Two containers that start at
once therefore never migrate together: the second waits, then reads the
revision the first committed and finds nothing left to do. The migrations
run in one transaction, so the lock covers all of them. SQLite has no
advisory locks and runs single-process, so there the lock is skipped.
"""

from logging.config import fileConfig

from sqlalchemy import Connection
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text

# ── ORM models ────────────────────────────────────────────────────────
# This import populates Base.metadata with all table definitions.
# Add new models to alembic_imports.py, never import them directly here.
import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from alembic import context
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.autogenerate_filters import (
    compare_server_default,
)
from src.modules.platform.adapters.outbound.persistence.autogenerate_filters import include_object
from src.modules.platform.adapters.outbound.persistence.models.base import Base

# ── Settings ──────────────────────────────────────────────────────────
# Import settings first so DATABASE_URL is available before any models load.
from src.modules.platform.infrastructure.config.settings import cfg

# ── Alembic config ────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url with the value from Settings so alembic.ini
# doesn't need to contain the real DB credentials.
config.set_main_option("sqlalchemy.url", cfg.database.url)

# Set up Python logging from alembic.ini [loggers] section.
if config.config_file_name is not None:
    # disable_existing_loggers=False preserves the glados logger (and its
    # DatabaseLogHandler) which is set up before Alembic runs in main.py.
    # The default True would set glados.disabled=True, silently dropping
    # all log.info()/log.error() calls for the rest of the process lifetime.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


# ── Migration runners ─────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """
    Offline mode: emit SQL to stdout without a live DB connection.
    Useful for generating a migration script to review before applying.

    Run with: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=compare_server_default,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_locked(connection: Connection) -> None:
    """Runs the migrations in one transaction on `connection`, under the
    migration lock on Postgres."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=compare_server_default,
        include_object=include_object,
    )
    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(AdvisoryLockKey.MIGRATION)}
            )
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: connect to the DB and apply migrations directly.
    This is what runs on application startup via init_db.run_migrations().

    A caller driving Alembic programmatically (a test, notably) can hand in
    an already-open connection via `config.attributes["connection"]`, the
    documented Alembic pattern for running migrations against a connection
    it does not own, instead of letting this function build its own engine
    from `sqlalchemy.url`. When present, that connection is reused as-is and
    no engine is created here.
    """
    attributes_connection = config.attributes.get("connection")
    if attributes_connection is not None:
        _run_locked(attributes_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # use NullPool in migrations, no connection reuse needed
    )

    with connectable.connect() as connection:
        _run_locked(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
