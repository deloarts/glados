"""
Concrete implementation of IPasskeyRepository using SQLAlchemy.
Writes flush and never commit; the calling use case owns the transaction.
"""

from typing import Any
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_passkey_model import (
    UserPasskeyOrmModel,
)
from src.modules.platform.domain.entities.passkey import Passkey
from src.modules.platform.ports.outbound.repositories.passkey_repository import IPasskeyRepository


def _orm_to_entity(orm: UserPasskeyOrmModel) -> Passkey:
    return Passkey(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        credential_id=orm.credential_id,
        public_key=orm.public_key,
        sign_count=orm.sign_count,
        name=orm.name,
        created_at=utc_aware(orm.created_at),
        last_used_at=utc_aware(orm.last_used_at),
        transports=list(orm.transports or []),
        backed_up=orm.backed_up,
    )


def _entity_to_orm_dict(passkey: Passkey) -> dict[str, Any]:
    return {
        "user_id": passkey.user_id,
        "credential_id": passkey.credential_id,
        "public_key": passkey.public_key,
        "sign_count": passkey.sign_count,
        "name": passkey.name,
        "transports": list(passkey.transports),
        "backed_up": passkey.backed_up,
        "created_at": passkey.created_at,
        "last_used_at": passkey.last_used_at,
    }


class SqlAlchemyPasskeyRepository(IPasskeyRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_credential_id(self, credential_id: bytes) -> Passkey | None:
        orm = await self._db.scalar(
            select(UserPasskeyOrmModel)
            .where(UserPasskeyOrmModel.credential_id == credential_id)
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_for_user(self, user_id: int, public_id: UUID) -> Passkey | None:
        orm = await self._db.scalar(
            select(UserPasskeyOrmModel)
            .where(
                UserPasskeyOrmModel.user_id == user_id,
                UserPasskeyOrmModel.public_id == public_id,
            )
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def list_for_user(self, user_id: int) -> list[Passkey]:
        q = (
            select(UserPasskeyOrmModel)
            .where(UserPasskeyOrmModel.user_id == user_id)
            .order_by(UserPasskeyOrmModel.id.desc())
        )
        return [_orm_to_entity(o) for o in (await self._db.scalars(q)).all()]

    async def save(self, passkey: Passkey) -> Passkey:
        if passkey.id == 0:
            orm = UserPasskeyOrmModel(**_entity_to_orm_dict(passkey))
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(UserPasskeyOrmModel).where(UserPasskeyOrmModel.id == passkey.id).limit(1)
        )
        if not existing:
            raise ValueError(f"UserPasskeyOrmModel id={passkey.id} not found.")
        for k, v in _entity_to_orm_dict(passkey).items():
            setattr(existing, k, v)
        await self._db.flush()
        await self._db.refresh(existing)
        return _orm_to_entity(existing)

    async def delete_by_public_id(self, user_id: int, public_id: UUID) -> bool:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                delete(UserPasskeyOrmModel).where(
                    UserPasskeyOrmModel.user_id == user_id,
                    UserPasskeyOrmModel.public_id == public_id,
                )
            ),
        )
        return result.rowcount > 0

    async def delete_all_for_user(self, user_id: int) -> int:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                delete(UserPasskeyOrmModel).where(UserPasskeyOrmModel.user_id == user_id)
            ),
        )
        return result.rowcount
