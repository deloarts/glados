"""
Database engines and session factories. This is the only file allowed to
construct a SQLAlchemy engine. The application runs on the async engine and
`SessionLocal` (AsyncSession); the background log writer, which runs on its
own thread, keeps a small synchronous engine of its own.

No CRUD imports. No schema imports. No business logic.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.modules.platform.adapters.outbound.persistence.changer_tracking import (
    register_changer_tracking,
)
from src.modules.platform.adapters.outbound.persistence.constraint_violation import (
    register_constraint_violation_translation,
)
from src.modules.platform.adapters.outbound.persistence.db_observability import (
    register_db_observability,
)
from src.modules.platform.adapters.outbound.persistence.edit_version_tracking import (
    register_edit_version_tracking,
)
from src.modules.platform.infrastructure.config.settings import DatabaseSettings
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.process_identity import worker_identity

# ── Engine ────────────────────────────────────────────────────────────
#
# Pool and timeout options are Postgres only. The test suite's SQLite file
# runs on aiosqlite with NullPool instead, so no connection is ever reused
# across the separate event loops pytest gives each test.
#
# Pool size, overflow and wait time come from DatabaseSettings so the total
# across gunicorn workers can be sized against the server's max_connections.
# pool_pre_ping survives Postgres container restarts that would otherwise
# leave stale connections in the pool; pool_recycle stays under any idle
# connection limit between the app and the server.
#
# Every connection starts with statement, lock and idle-in-transaction
# timeouts, so a runaway query or an abandoned transaction cannot hold
# locks or a pool slot indefinitely, and with an application_name that
# makes each worker's connections identifiable in pg_stat_activity.


def postgres_connect_args(settings: DatabaseSettings, application_name: str) -> dict[str, str]:
    """libpq connection parameters carrying the server-side timeouts."""
    options = " ".join(
        f"-c {name}={seconds}s"
        for name, seconds in (
            ("statement_timeout", settings.statement_timeout_seconds),
            ("lock_timeout", settings.lock_timeout_seconds),
            ("idle_in_transaction_session_timeout", settings.idle_in_transaction_timeout_seconds),
        )
    )
    return {"options": options, "application_name": application_name[:63]}


_pool_options: dict[str, object] = (
    {
        "pool_size": cfg.database.pool_size,
        "max_overflow": cfg.database.max_overflow,
        "pool_timeout": cfg.database.pool_timeout_seconds,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "connect_args": postgres_connect_args(cfg.database, f"glados-{worker_identity()}"),
    }
    if cfg.database.url.startswith("postgresql")
    else {"poolclass": NullPool}
)

engine: AsyncEngine = create_async_engine(
    cfg.database.async_url,
    echo=cfg.debug,  # logs all SQL statements when debug=True
    **_pool_options,
)
register_db_observability(engine.sync_engine, cfg.database.slow_query_threshold_ms)
register_constraint_violation_translation(engine.sync_engine)

# expire_on_commit=False: objects keep their loaded state after a commit
# instead of reloading every attribute on next access. Repositories that
# need database-generated values after a write reload the row explicitly
# (populate_existing), and an AsyncSession cannot do the implicit reload at
# all, so nothing may rely on it.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)
register_changer_tracking(SessionLocal)
register_edit_version_tracking(SessionLocal)


# ── Log writer engine ─────────────────────────────────────────────────
#
# A single connection reserved for the background log writer
# (DatabaseLogHandler). Keeping it out of the request pool means a burst of
# log lines never competes with requests for a pooled connection, and an
# exhausted request pool can still have its errors logged.

log_engine = create_engine(
    cfg.database.url,
    **(
        {
            "pool_size": 1,
            "max_overflow": 0,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "connect_args": postgres_connect_args(cfg.database, f"glados-log-{worker_identity()}"),
        }
        if cfg.database.url.startswith("postgresql")
        else {}
    ),
)

LogSessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=log_engine,
)
