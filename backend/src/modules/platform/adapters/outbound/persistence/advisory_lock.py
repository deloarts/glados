"""Postgres advisory locks that work with the connection pool.

A session-level lock is tied to the backend connection, and returning a
connection to the pool only rolls back, so the lock would stay held and
pass to whichever caller reuses that connection. These helpers therefore
take a transaction-scoped lock on a connection opened and closed by hand,
never a Session, so it releases when the transaction ends.

A lock-holding connection sits idle in its transaction for as long as the
guarded work runs on a separate session, which is exactly what the
server-wide idle_in_transaction_session_timeout (session.py) exists to
kill. `hold_lock_transaction` lifts that limit for the lock connection
only, and the blocking variant also lifts lock_timeout so a waiter queues
until the holder finishes; statement_timeout still caps the wait.

Every fixed key lives in AdvisoryLockKey, so no two lock sites can collide.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import IntEnum
from enum import unique

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine


@unique
class AdvisoryLockKey(IntEnum):
    """The app's advisory-lock keys, one per lock site. A namespace member is
    not a lock on its own: PDM_FILE_NAMESPACE is the upper 32 bits of a
    per-file key (pdm_file_lock.py), and QUEUE_SEQUENCE_NAMESPACE is the first
    key of the two-key queue lock (production_order_repository.py) and
    TIME_BUDGET_NAMESPACE that of the per-project time budget lock
    (production_lot_repository/lot.py), which Postgres keeps in a key space
    apart from the single-key locks."""

    OUTBOX_RELAY = 0x0107B0
    BACKUP_RUN = 0x0107B1
    NOTIFICATION_TICK = 0x0107B2
    SCHEDULE_RECOMPUTE = 0x0107B3
    PDM_POLL = 0x0107B4
    RETENTION_PURGE = 0x0107B5
    PDM_FILE_NAMESPACE = 0x0107B6
    # Held by alembic/env.py for the whole migration transaction, so two
    # containers starting at once never migrate the same database together.
    MIGRATION = 0x0107B7
    AGENT_TOKEN_SWEEP = 0x0107B8
    MEETING_NOTIFICATION_FLUSH = 0x0107B9
    MEETING_MAINTENANCE = 0x0107BA
    INIT_DB_SEED = 7874131
    QUEUE_SEQUENCE_NAMESPACE = 1901054801
    TIME_BUDGET_NAMESPACE = 1901054802


async def hold_lock_transaction(conn: AsyncConnection) -> None:
    """Opens the lock connection's transaction and exempts it from the idle
    in transaction timeout, for this transaction only."""
    await conn.begin()
    await conn.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))


async def try_xact_lock(conn: AsyncConnection, key: int) -> bool:
    """Tries the transaction-scoped lock on `conn` and returns whether it
    was taken."""
    result = await conn.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": int(key)})
    return bool(result.scalar())


@asynccontextmanager
async def advisory_lock(bind: AsyncEngine, key: int) -> AsyncIterator[bool]:
    """Tries the lock on its own connection and yields whether it was
    taken. On SQLite, which is single-process, it always yields True. The
    transaction is always rolled back on exit, which releases the lock.
    """
    if bind.dialect.name != "postgresql":
        yield True
        return

    conn = await bind.connect()
    try:
        await hold_lock_transaction(conn)
        yield await try_xact_lock(conn, key)
    finally:
        # The connection returns to the pool even if the rollback raises.
        try:
            await conn.rollback()
        finally:
            await conn.close()


@asynccontextmanager
async def advisory_lock_blocking(bind: AsyncEngine, key: int) -> AsyncIterator[None]:
    """Like advisory_lock(), but waits until the lock is acquired, for real
    mutual exclusion over a unit of work.
    """
    if bind.dialect.name != "postgresql":
        yield
        return

    conn = await bind.connect()
    try:
        await hold_lock_transaction(conn)
        await conn.execute(text("SET LOCAL lock_timeout = 0"))
        await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(key)})
        yield
    finally:
        try:
            await conn.rollback()
        finally:
            await conn.close()
