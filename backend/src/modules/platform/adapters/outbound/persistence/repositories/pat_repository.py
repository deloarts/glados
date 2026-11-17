"""
Concrete implementation of IPatRepository using SQLAlchemy.
Writes flush and never commit; the calling use case owns the transaction.
"""

from typing import Any
from typing import cast

from sqlalchemy import CursorResult
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.pat_repository import PatFilterDto
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: PatOrmModel) -> PersonalAccessToken:
    created = utc_aware(orm.created)
    assert created is not None  # non-null column
    return PersonalAccessToken(
        id=orm.id,
        public_id=orm.public_id,
        name=orm.name,
        token_hash=orm.token_hash,
        token_prefix=orm.token_prefix,
        user_id=orm.user_id,
        permissions=list(orm.permissions or []),
        created=created,
        expires_at=utc_aware(orm.expires_at),
        revoked_at=utc_aware(orm.revoked_at),
    )


def _entity_to_orm_dict(token: PersonalAccessToken) -> dict[str, Any]:
    return {
        "name": token.name,
        "token_hash": token.token_hash,
        "token_prefix": token.token_prefix,
        "user_id": token.user_id,
        "permissions": list(token.permissions),
        "created": token.created,
        "expires_at": token.expires_at,
        "revoked_at": token.revoked_at,
    }


class SqlAlchemyPatRepository(IPatRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> PersonalAccessToken | None:
        orm = await self._db.scalar(by_id(PatOrmModel, id).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_by_token_hash(self, token_hash: str) -> PersonalAccessToken | None:
        orm = await self._db.scalar(
            select(PatOrmModel).where(PatOrmModel.token_hash == token_hash).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_multi_for_user(
        self, user_id: int, filters: PatFilterDto
    ) -> tuple[int, list[PersonalAccessToken]]:
        zone = await date_filter_zone(self._db, filters.created_from, filters.created_to)
        q = select(PatOrmModel).where(PatOrmModel.user_id == user_id)
        if not filters.include_revoked:
            q = q.where(PatOrmModel.revoked_at.is_(None))
        if filters.search:
            q = q.where(contains_ci(PatOrmModel.name, filters.search))
        if filters.token_prefix:
            q = q.where(contains_ci(PatOrmModel.token_prefix, filters.token_prefix))
        if filters.created_from:
            q = q.where(PatOrmModel.created >= day_start_utc(filters.created_from, zone))
        if filters.created_to:
            q = q.where(PatOrmModel.created < day_after_utc(filters.created_to, zone))
        if filters.expiry == "never":
            q = q.where(PatOrmModel.expires_at.is_(None))
        elif filters.expiry == "expired":
            q = q.where(PatOrmModel.expires_at <= now_utc())
        elif filters.expiry == "active":
            q = q.where(PatOrmModel.expires_at > now_utc())
        elif filters.expiry == "unexpired":
            q = q.where(or_(PatOrmModel.expires_at.is_(None), PatOrmModel.expires_at > now_utc()))

        _sort_column_map = {
            "id": PatOrmModel.id,
            "name": PatOrmModel.name,
            "created": PatOrmModel.created,
            "expires_at": PatOrmModel.expires_at,
        }
        # Without an `order_by` the list sorts by `id desc`, newest first.
        sort_col = _sort_column_map.get(filters.order_by or "id", PatOrmModel.id)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
        )
        return total, [_orm_to_entity(o) for o in rows]

    async def save(self, token: PersonalAccessToken) -> PersonalAccessToken:
        """Flushes without committing; the calling use case commits."""
        if token.id == 0:
            orm = PatOrmModel(**_entity_to_orm_dict(token))
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(PatOrmModel).where(PatOrmModel.id == token.id).limit(1)
        )
        if not existing:
            raise ValueError(f"PatOrmModel id={token.id} not found.")
        orm = existing
        for k, v in _entity_to_orm_dict(token).items():
            setattr(orm, k, v)
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def list_unrevoked_unexpired(
        self, user_id: int | None = None
    ) -> list[PersonalAccessToken]:
        q = (
            select(PatOrmModel)
            .where(
                PatOrmModel.revoked_at.is_(None),
                or_(PatOrmModel.expires_at.is_(None), PatOrmModel.expires_at > now_utc()),
            )
            .order_by(PatOrmModel.id)
        )
        if user_id is not None:
            q = q.where(PatOrmModel.user_id == user_id)
        return [_orm_to_entity(o) for o in (await self._db.execute(q)).scalars().all()]

    async def revoke_all_for_user(self, user_id: int) -> int:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(PatOrmModel)
                .where(PatOrmModel.user_id == user_id, PatOrmModel.revoked_at.is_(None))
                .values(revoked_at=now_utc())
            ),
        )
        return result.rowcount
