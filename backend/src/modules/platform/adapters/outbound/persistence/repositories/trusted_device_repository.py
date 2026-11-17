"""
Concrete implementation of ITrustedDeviceRepository using SQLAlchemy.
Writes flush and never commit; the calling use case owns the transaction.
"""

from typing import Any
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.user_trusted_device_model import (
    UserTrustedDeviceOrmModel,
)
from src.modules.platform.domain.entities.trusted_device import TrustedDevice
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: UserTrustedDeviceOrmModel) -> TrustedDevice:
    created_at = utc_aware(orm.created_at)
    last_used_at = utc_aware(orm.last_used_at)
    expires_at = utc_aware(orm.expires_at)
    assert (  # non-null columns
        created_at is not None and last_used_at is not None and expires_at is not None
    )
    return TrustedDevice(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        token_hash=orm.token_hash,
        created_at=created_at,
        last_used_at=last_used_at,
        expires_at=expires_at,
        user_agent=orm.user_agent,
        revoked_at=utc_aware(orm.revoked_at),
    )


def _entity_to_orm_dict(device: TrustedDevice) -> dict[str, Any]:
    return {
        "user_id": device.user_id,
        "token_hash": device.token_hash,
        "created_at": device.created_at,
        "last_used_at": device.last_used_at,
        "expires_at": device.expires_at,
        "user_agent": device.user_agent,
        "revoked_at": device.revoked_at,
    }


class SqlAlchemyTrustedDeviceRepository(ITrustedDeviceRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_token_hash(self, token_hash: str) -> TrustedDevice | None:
        orm = await self._db.scalar(
            select(UserTrustedDeviceOrmModel)
            .where(UserTrustedDeviceOrmModel.token_hash == token_hash)
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def list_for_user(self, user_id: int) -> list[TrustedDevice]:
        q = (
            select(UserTrustedDeviceOrmModel)
            .where(
                UserTrustedDeviceOrmModel.user_id == user_id,
                UserTrustedDeviceOrmModel.revoked_at.is_(None),
                UserTrustedDeviceOrmModel.expires_at > now_utc(),
            )
            .order_by(UserTrustedDeviceOrmModel.id.desc())
        )
        return [_orm_to_entity(o) for o in (await self._db.scalars(q)).all()]

    async def save(self, device: TrustedDevice) -> TrustedDevice:
        if device.id == 0:
            orm = UserTrustedDeviceOrmModel(**_entity_to_orm_dict(device))
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(UserTrustedDeviceOrmModel)
            .where(UserTrustedDeviceOrmModel.id == device.id)
            .limit(1)
        )
        if not existing:
            raise ValueError(f"UserTrustedDeviceOrmModel id={device.id} not found.")
        for k, v in _entity_to_orm_dict(device).items():
            setattr(existing, k, v)
        await self._db.flush()
        await self._db.refresh(existing)
        return _orm_to_entity(existing)

    async def revoke_by_public_id(self, user_id: int, public_id: UUID) -> bool:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(UserTrustedDeviceOrmModel)
                .where(
                    UserTrustedDeviceOrmModel.user_id == user_id,
                    UserTrustedDeviceOrmModel.public_id == public_id,
                    UserTrustedDeviceOrmModel.revoked_at.is_(None),
                )
                .values(revoked_at=now_utc())
            ),
        )
        return result.rowcount > 0

    async def revoke_all_for_user(self, user_id: int) -> int:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(UserTrustedDeviceOrmModel)
                .where(
                    UserTrustedDeviceOrmModel.user_id == user_id,
                    UserTrustedDeviceOrmModel.revoked_at.is_(None),
                )
                .values(revoked_at=now_utc())
            ),
        )
        return result.rowcount
