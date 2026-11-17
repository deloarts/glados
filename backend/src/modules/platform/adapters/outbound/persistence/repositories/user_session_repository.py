"""
Concrete implementation of IUserSessionRepository using SQLAlchemy.
Writes flush and never commit; the calling use case owns the transaction.
"""

from datetime import datetime
from typing import Any
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_session_model import (
    UserSessionOrmModel,
)
from src.modules.platform.domain.entities.user_session import UserSession
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: UserSessionOrmModel) -> UserSession:
    created_at = utc_aware(orm.created_at)
    last_seen_at = utc_aware(orm.last_seen_at)
    assert created_at is not None and last_seen_at is not None  # non-null columns
    return UserSession(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        created_at=created_at,
        last_seen_at=last_seen_at,
        user_agent=orm.user_agent,
        ip=orm.ip,
        revoked_at=utc_aware(orm.revoked_at),
    )


def _entity_to_orm_dict(session: UserSession) -> dict[str, Any]:
    return {
        "user_id": session.user_id,
        "created_at": session.created_at,
        "last_seen_at": session.last_seen_at,
        "user_agent": session.user_agent,
        "ip": session.ip,
        "revoked_at": session.revoked_at,
    }


class SqlAlchemyUserSessionRepository(IUserSessionRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_public_id(self, public_id: UUID) -> UserSession | None:
        orm = await self._db.scalar(
            select(UserSessionOrmModel).where(UserSessionOrmModel.public_id == public_id).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def list_for_user(self, user_id: int) -> list[UserSession]:
        q = (
            select(UserSessionOrmModel)
            .where(
                UserSessionOrmModel.user_id == user_id,
                UserSessionOrmModel.revoked_at.is_(None),
            )
            .order_by(UserSessionOrmModel.last_seen_at.desc())
        )
        return [_orm_to_entity(o) for o in (await self._db.scalars(q)).all()]

    async def save(self, session: UserSession) -> UserSession:
        if session.id == 0:
            orm = UserSessionOrmModel(**_entity_to_orm_dict(session))
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(UserSessionOrmModel).where(UserSessionOrmModel.id == session.id).limit(1)
        )
        if not existing:
            raise ValueError(f"UserSessionOrmModel id={session.id} not found.")
        for k, v in _entity_to_orm_dict(session).items():
            setattr(existing, k, v)
        await self._db.flush()
        await self._db.refresh(existing)
        return _orm_to_entity(existing)

    async def touch_last_seen(self, public_id: UUID, when: datetime) -> None:
        await self._db.execute(
            update(UserSessionOrmModel)
            .where(UserSessionOrmModel.public_id == public_id)
            .values(last_seen_at=when)
        )

    async def revoke_by_public_id(self, user_id: int, public_id: UUID) -> bool:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(UserSessionOrmModel)
                .where(
                    UserSessionOrmModel.user_id == user_id,
                    UserSessionOrmModel.public_id == public_id,
                    UserSessionOrmModel.revoked_at.is_(None),
                )
                .values(revoked_at=now_utc())
            ),
        )
        return result.rowcount > 0

    async def revoke_all_for_user(self, user_id: int) -> int:
        return await self.revoke_all_for_user_except(user_id, keep_public_id=None)

    async def revoke_all_for_user_except(self, user_id: int, keep_public_id: UUID | None) -> int:
        stmt = update(UserSessionOrmModel).where(
            UserSessionOrmModel.user_id == user_id,
            UserSessionOrmModel.revoked_at.is_(None),
        )
        if keep_public_id is not None:
            stmt = stmt.where(UserSessionOrmModel.public_id != keep_public_id)
        result = cast(CursorResult[Any], await self._db.execute(stmt.values(revoked_at=now_utc())))
        return result.rowcount
