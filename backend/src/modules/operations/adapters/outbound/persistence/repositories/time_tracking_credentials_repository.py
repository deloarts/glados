"""
Concrete implementation of IUserTimeTrackingCredentialsRepository using
SQLAlchemy. The user name is encrypted and decrypted by the EncryptedString
column type, so it is plaintext here; a value no configured key decrypts
reads as None. The sealed credentials are stored as they come. Writes that
only change Glados state (the auth-failed mark, clearing the sealed value)
update their own column, so an undecryptable row is never overwritten with
NULLs.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.operations.adapters.outbound.persistence.models.user_time_tracking_credentials_model import (
    UserTimeTrackingCredentialsOrmModel,
)
from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.errors import TimeTrackingUserAlreadyLinkedError
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import count_rows

_Model = UserTimeTrackingCredentialsOrmModel


def _orm_to_entity(orm: UserTimeTrackingCredentialsOrmModel) -> UserTimeTrackingCredentials:
    return UserTimeTrackingCredentials(
        id=orm.id,
        public_id=orm.public_id,
        user_id=orm.user_id,
        time_tracking_user=orm.time_tracking_user or None,
        time_tracking_sealed_credentials=orm.time_tracking_sealed_credentials or None,
        time_tracking_binding=orm.time_tracking_binding,
        time_tracking_credential_key_id=orm.time_tracking_credential_key_id,
        time_tracking_user_fingerprint=orm.time_tracking_user_fingerprint,
        time_tracking_user_fingerprint_key_id=orm.time_tracking_user_fingerprint_key_id,
        time_tracking_auth_failed_at=(utc_aware(orm.time_tracking_auth_failed_at)),
        time_tracking_consent_at=utc_aware(orm.time_tracking_consent_at),
        time_tracking_consent_version=orm.time_tracking_consent_version,
        created_at=utc_aware(orm.created_at),
        updated_at=utc_aware(orm.updated_at),
    )


def _entity_to_dict(c: UserTimeTrackingCredentials) -> dict[str, Any]:
    return {
        "user_id": c.user_id,
        "time_tracking_user": c.time_tracking_user,
        "time_tracking_sealed_credentials": c.time_tracking_sealed_credentials,
        "time_tracking_binding": c.time_tracking_binding,
        "time_tracking_credential_key_id": c.time_tracking_credential_key_id,
        "time_tracking_user_fingerprint": c.time_tracking_user_fingerprint,
        "time_tracking_user_fingerprint_key_id": c.time_tracking_user_fingerprint_key_id,
        "time_tracking_auth_failed_at": c.time_tracking_auth_failed_at,
        "time_tracking_consent_at": c.time_tracking_consent_at,
        "time_tracking_consent_version": c.time_tracking_consent_version,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


class SqlAlchemyUserTimeTrackingCredentialsRepository:
    """Implements IUserTimeTrackingCredentialsRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_user(self, user_id: int) -> UserTimeTrackingCredentials | None:
        orm = await self._db.scalar(
            select(_Model)
            .where(_Model.user_id == user_id)
            .execution_options(populate_existing=True)
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def list_all(self) -> list[UserTimeTrackingCredentials]:
        rows = await self._db.scalars(select(_Model).order_by(_Model.user_id))
        return [_orm_to_entity(orm) for orm in rows]

    async def exists_for_user(self, user_id: int) -> bool:
        return await count_rows(self._db, select(_Model.id).where(_Model.user_id == user_id)) > 0

    async def is_fingerprint_taken_by_other_user(self, fingerprint: str, user_id: int) -> bool:
        stmt = select(_Model.id).where(
            _Model.time_tracking_user_fingerprint == fingerprint, _Model.user_id != user_id
        )
        return await count_rows(self._db, stmt) > 0

    async def save(self, credentials: UserTimeTrackingCredentials) -> UserTimeTrackingCredentials:
        data = _entity_to_dict(credentials)
        orm = await self._db.scalar(
            select(_Model).where(_Model.user_id == credentials.user_id).limit(1)
        )
        if orm is None:
            orm = _Model(**data)
            self._db.add(orm)
        else:
            data.pop("created_at")
            for key, value in data.items():
                setattr(orm, key, value)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            if "fingerprint" in str(exc.orig).lower():
                raise TimeTrackingUserAlreadyLinkedError(
                    "This time tracking user is already linked to another Glados account."
                ) from exc
            raise
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def mark_auth_failed(self, user_id: int, at: datetime) -> None:
        await self._db.execute(
            update(_Model).where(_Model.user_id == user_id).values(time_tracking_auth_failed_at=at)
        )
        await self._db.flush()

    async def clear_sealed(self, user_id: int) -> None:
        await self._db.execute(
            update(_Model)
            .where(_Model.user_id == user_id)
            .values(time_tracking_sealed_credentials=None)
        )
        await self._db.flush()

    async def delete_for_user(self, user_id: int) -> bool:
        result = await self._db.execute(delete(_Model).where(_Model.user_id == user_id))
        await self._db.flush()
        return bool(getattr(result, "rowcount", 0))

    async def delete_all(self) -> int:
        result = await self._db.execute(delete(_Model))
        await self._db.flush()
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_count(self) -> int:
        return await count_rows(self._db, select(_Model.id))
