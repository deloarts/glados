"""
Concrete implementation of ILogRepository using SQLAlchemy + Postgres.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.platform.ports.outbound.repositories.log_repository import ILogRepository
from src.modules.platform.ports.outbound.repositories.log_repository import LogFilterDto


def _orm_to_entity(orm: LogOrmModel) -> LogEntry:
    return LogEntry(
        id=orm.id,
        public_id=orm.public_id,
        timestamp=orm.timestamp,
        user_id=orm.user_id,
        username=orm.username,
        level=orm.level,
        message=orm.message,
        method=orm.method,
        path=orm.path,
        status_code=orm.status_code,
        request_id=orm.request_id,
    )


def persist_log_batch(db: Session, entries: list[LogEntry]) -> None:
    """Adds a batch of app log records to a SYNC session, which the caller
    commits as one transaction. Used only by the background log writer,
    which runs on its own thread with its own small synchronous engine (see
    session.py) and never needs the stored rows back."""
    db.add_all(
        LogOrmModel(
            timestamp=e.timestamp,
            user_id=e.user_id,
            username=e.username,
            level=e.level,
            message=e.message,
            method=e.method,
            path=e.path,
            status_code=e.status_code,
            request_id=e.request_id,
        )
        for e in entries
    )


class SqlAlchemyLogRepository(ILogRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_multi(self, filters: LogFilterDto) -> tuple[int, list[LogEntry]]:
        q = select(LogOrmModel)

        if filters.user_id is not None:
            q = q.where(LogOrmModel.user_id == filters.user_id)
        if filters.username_contains is not None:
            q = q.where(contains_ci(LogOrmModel.username, filters.username_contains))
        if filters.status_code is not None:
            q = q.where(LogOrmModel.status_code == filters.status_code)
        if filters.level is not None:
            q = q.where(LogOrmModel.level == filters.level.upper())
        if filters.method is not None:
            q = q.where(LogOrmModel.method == filters.method.upper())
        if filters.path_contains is not None:
            q = q.where(LogOrmModel.path.contains(filters.path_contains))
        if filters.message_contains is not None:
            q = q.where(contains_ci(LogOrmModel.message, filters.message_contains))
        if filters.request_id is not None:
            q = q.where(LogOrmModel.request_id == filters.request_id)
        if filters.from_timestamp is not None:
            q = q.where(LogOrmModel.timestamp >= filters.from_timestamp)
        if filters.to_timestamp is not None:
            q = q.where(LogOrmModel.timestamp <= filters.to_timestamp)

        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            LogOrmModel.timestamp.desc(),
            LogOrmModel.id.desc(),
        )
        return total, [_orm_to_entity(o) for o in rows]

    async def save(self, entry: LogEntry) -> LogEntry:
        orm = LogOrmModel(
            timestamp=entry.timestamp,
            user_id=entry.user_id,
            username=entry.username,
            level=entry.level,
            message=entry.message,
            method=entry.method,
            path=entry.path,
            status_code=entry.status_code,
            request_id=entry.request_id,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)
