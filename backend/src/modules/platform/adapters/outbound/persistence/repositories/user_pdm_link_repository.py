"""
Concrete implementation of IUserPdmLinkRepository using SQLAlchemy.
"""

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_pdm_link_model import (
    UserPdmLinkOrmModel,
)
from src.modules.platform.domain.entities.user_pdm_link import UserPdmLink
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: UserPdmLinkOrmModel) -> UserPdmLink:
    return UserPdmLink(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        pdm_user_id=orm.pdm_user_id,
        pdm_username=orm.pdm_username,
        linked_at=utc_aware(orm.linked_at),
    )


class SqlAlchemyUserPdmLinkRepository:
    """Implements IUserPdmLinkRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_all(self) -> list[UserPdmLink]:
        rows = (await self._db.scalars(select(UserPdmLinkOrmModel))).all()
        return [_orm_to_entity(r) for r in rows]

    async def list_by_user(self, user_id: int) -> list[UserPdmLink]:
        rows = (
            await self._db.scalars(
                select(UserPdmLinkOrmModel)
                .where(UserPdmLinkOrmModel.user_id == user_id)
                .order_by(UserPdmLinkOrmModel.linked_at)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_pdm_user_id(self, pdm_user_id: int) -> UserPdmLink | None:
        orm = await self._db.scalar(
            select(UserPdmLinkOrmModel)
            .where(UserPdmLinkOrmModel.pdm_user_id == pdm_user_id)
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def upsert(self, *, pdm_user_id: int, user_id: int, pdm_username: str) -> UserPdmLink:
        existing = await self._db.scalar(
            select(UserPdmLinkOrmModel)
            .where(UserPdmLinkOrmModel.pdm_user_id == pdm_user_id)
            .limit(1)
        )
        linked_at = now_utc()
        if existing is None:
            orm = UserPdmLinkOrmModel(
                user_id=user_id,
                pdm_user_id=pdm_user_id,
                pdm_username=pdm_username,
                linked_at=linked_at,
            )
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing.user_id = user_id
        existing.pdm_username = pdm_username
        existing.linked_at = linked_at
        await self._db.flush()
        await self._db.refresh(existing)
        return _orm_to_entity(existing)

    async def delete_by_pdm_user_id(self, pdm_user_id: int) -> None:
        await self._db.execute(
            delete(UserPdmLinkOrmModel).where(UserPdmLinkOrmModel.pdm_user_id == pdm_user_id)
        )
        await self._db.flush()
