"""Transactional outbox: the producer-side IEventBus implementation and the
relay-side IEventOutbox implementation, both over `event_outbox_table`.

Ordering rule (the whole point of the transactional mode):

    An event staged through IEventBus BEFORE commit() is committed
    atomically with the write. An event staged AFTER commit() is LOST:
    get_db() never commits, so a session.add() left pending at request end
    is discarded. Publish before commit, always.

That rule is enforced statically by tests/unit/test_architecture.py
(test_no_use_case_publishes_after_committing_its_unit_of_work) and observed
at runtime by the EVENT_OUTBOX_ABANDONED tripwire at the bottom of this
file (register_outbox_tripwire, attached to SessionLocal in main.py next to
register_change_tracking).

The bus never commits: the staged row joins the caller's open transaction,
so the write and its event commit or roll back together when the use case
commits its unit of work. It is wired via get_transactional_event_bus.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import hold_lock_transaction
from src.modules.platform.adapters.outbound.persistence.advisory_lock import try_xact_lock
from src.modules.platform.adapters.outbound.persistence.models.event_outbox_model import (
    EventOutboxOrmModel,
)
from src.modules.platform.infrastructure.events.codec import serialize
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_outbox_port import OutboxMessage
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc

_MAX_ERROR_CHARS = 500  # a driver traceback string must not become the payload


class OutboxEventBus:
    """IEventBus over event_outbox_table. See the module docstring."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, event: DomainEvent) -> None:
        """Stages `event`. Never raises, because a broken outbox must not fail
        the request; a failure is logged and the event dropped."""
        try:
            fields = serialize(event)
            self._session.add(
                EventOutboxOrmModel(
                    event_id=uuid4().hex,
                    event_type=fields["type"],
                    payload=fields["payload"],
                    created=now_utc(),
                )
            )
        except Exception:
            # The caller owns the transaction, and rolling back here would
            # silently discard its work.
            log.exception("Failed to stage event %r in the outbox; dropping it.", event)


class SqlAlchemyEventOutbox:
    """IEventOutbox over event_outbox_table, for the relay. try_lock and
    release_lock hold the relay slot's lock on their own connection across
    separate calls, released every tick; a crashed process releases it with
    its connection. release_lock is not part of the port.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._lock_conn: AsyncConnection | None = None

    async def try_lock(self) -> bool:
        dialect = self._db.get_bind().dialect.name
        if dialect != "postgresql":
            # SQLite is single-process, so there is nothing to lock.
            return True

        # A dedicated connection, never the session (see advisory_lock.py).
        # SessionLocal is always bound to the engine.
        conn = await cast(AsyncEngine, self._db.bind).connect()
        try:
            await hold_lock_transaction(conn)
            locked = await try_xact_lock(conn, AdvisoryLockKey.OUTBOX_RELAY)
        except Exception:
            try:
                await conn.rollback()
            finally:
                await conn.close()
            raise

        if not locked:
            try:
                await conn.rollback()
            finally:
                await conn.close()
            return False

        self._lock_conn = conn
        return True

    async def release_lock(self) -> None:
        """Releases the lock and returns its connection. Idempotent."""
        if self._lock_conn is None:
            return
        conn = self._lock_conn
        self._lock_conn = None
        try:
            await conn.rollback()
        finally:
            await conn.close()

    async def fetch_unpublished(self, limit: int) -> list[OutboxMessage]:
        rows = (
            await self._db.scalars(
                select(EventOutboxOrmModel)
                .where(EventOutboxOrmModel.published_at.is_(None))
                .order_by(EventOutboxOrmModel.id)
                .limit(limit)
            )
        ).all()
        return [
            OutboxMessage(
                id=row.id,
                event_id=row.event_id,
                event_type=row.event_type,
                payload=row.payload,
                attempts=row.attempts,
            )
            for row in rows
        ]

    async def fetch_published(
        self,
        *,
        since: datetime,
        until: datetime | None,
        event_types: Sequence[str],
        after_id: int,
        limit: int,
    ) -> list[OutboxMessage]:
        """Relayed rows published at or after `since` and before `until`,
        optionally of the given event types, in id order from just after
        `after_id`. Not part of the port: only `admin republish-outbox`
        reads published rows, to put them on the stream once more."""
        statement = (
            select(EventOutboxOrmModel)
            .where(
                EventOutboxOrmModel.published_at.is_not(None),
                EventOutboxOrmModel.published_at >= since,
                EventOutboxOrmModel.id > after_id,
            )
            .order_by(EventOutboxOrmModel.id)
            .limit(limit)
        )
        if until is not None:
            statement = statement.where(EventOutboxOrmModel.published_at < until)
        if event_types:
            statement = statement.where(EventOutboxOrmModel.event_type.in_(list(event_types)))
        rows = (await self._db.scalars(statement)).all()
        return [
            OutboxMessage(
                id=row.id,
                event_id=row.event_id,
                event_type=row.event_type,
                payload=row.payload,
                attempts=row.attempts,
            )
            for row in rows
        ]

    async def mark_published(self, ids: Sequence[int]) -> None:
        if not ids:
            return
        now = now_utc()
        for row in (
            await self._db.scalars(
                select(EventOutboxOrmModel).where(EventOutboxOrmModel.id.in_(list(ids)))
            )
        ).all():
            row.published_at = now
        await self._db.commit()

    async def record_failure(self, message_id: int, error: str) -> int:
        row = await self._db.get(EventOutboxOrmModel, message_id)
        if row is None:
            return 0
        row.attempts += 1
        row.last_error = error[:_MAX_ERROR_CHARS]
        attempts = row.attempts
        await self._db.commit()
        return attempts

    async def purge_published(self, older_than: datetime) -> int:
        rows = (
            await self._db.scalars(
                select(EventOutboxOrmModel).where(
                    EventOutboxOrmModel.published_at.is_not(None),
                    EventOutboxOrmModel.published_at < older_than,
                )
            )
        ).all()
        for row in rows:
            await self._db.delete(row)
        await self._db.commit()
        return len(rows)


def _abandoned_outbox_row(_session: Session, instance: object) -> None:
    """Logs an event row that was evicted without being flushed, so the
    event is lost. It catches a use case publishing after its commit, and
    also fires, accurately, when a transaction with staged events rolls
    back. Search the logs for EVENT_OUTBOX_ABANDONED.
    """
    if not isinstance(instance, EventOutboxOrmModel):
        return
    log.error(
        "EVENT_OUTBOX_ABANDONED type=%s event_id=%s -- staged but never committed; "
        "the event is lost. A use case published after its uow.commit().",
        instance.event_type,
        instance.event_id,
    )


def register_outbox_tripwire(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Attaches the tripwire to the sync Session class behind the factory,
    where ORM session events live. Call once at startup."""
    sync_cls: type[Session] = session_factory.class_.sync_session_class
    if not event.contains(sync_cls, "pending_to_transient", _abandoned_outbox_row):
        event.listen(sync_cls, "pending_to_transient", _abandoned_outbox_row)
