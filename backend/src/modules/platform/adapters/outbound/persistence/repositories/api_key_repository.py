"""
Concrete implementation of IApiKeyRepository using SQLAlchemy.
"""

from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import String
from sqlalchemy import cast
from sqlalchemy import not_
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.api_key_model import ApiKeyOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.domain.entities.api_key import ApiKey
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.shared_kernel.domain.services.clock import now_utc


def _orm_to_entity(orm: ApiKeyOrmModel) -> ApiKey:
    return ApiKey(
        id=orm.id,
        public_id=orm.public_id,
        name=orm.name,
        token_hash=orm.token_hash,
        token_prefix=orm.token_prefix,
        user_id=orm.user_id,
        permissions=list(orm.permissions or []),
        created_by_id=orm.created_by_id,
        created=utc_aware(orm.created),
        expires_at=utc_aware(orm.expires_at),
        revoked_at=utc_aware(orm.revoked_at),
    )


def _entity_to_orm_dict(key: ApiKey) -> dict[str, Any]:
    return {
        "name": key.name,
        "token_hash": key.token_hash,
        "token_prefix": key.token_prefix,
        "user_id": key.user_id,
        "permissions": list(key.permissions),
        "created_by_id": key.created_by_id,
        "created": key.created,
        "expires_at": key.expires_at,
        "revoked_at": key.revoked_at,
    }


def _holds_terminal_grant(holds: bool) -> ColumnElement[bool]:
    """Whether a key's grants include connect:terminals, which makes it a
    terminal key (ApiKey.is_terminal_key). The grants are a plain JSON list on
    both SQLite and Postgres, so the check matches the quoted grant in the
    column's text; a grant never contains a quote, so it cannot match a part
    of another one."""
    grants = cast(ApiKeyOrmModel.permissions, String)
    match = grants.contains(f'"{Permission.CONNECT_TERMINALS}"', autoescape=True)
    return match if holds else not_(match)


class SqlAlchemyApiKeyRepository(IApiKeyRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> ApiKey | None:
        orm = await self._db.scalar(by_id(ApiKeyOrmModel, id).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_by_token_hash(self, token_hash: str) -> ApiKey | None:
        orm = await self._db.scalar(
            select(ApiKeyOrmModel).where(ApiKeyOrmModel.token_hash == token_hash).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_multi(self, filters: ApiKeyFilterDto) -> tuple[int, list[ApiKey]]:
        zone = await date_filter_zone(self._db, filters.created_from, filters.created_to)
        q = select(ApiKeyOrmModel)
        if not filters.include_revoked:
            q = q.where(ApiKeyOrmModel.revoked_at.is_(None))
        if filters.search:
            q = q.where(contains_ci(ApiKeyOrmModel.name, filters.search))
        if filters.token_prefix:
            q = q.where(contains_ci(ApiKeyOrmModel.token_prefix, filters.token_prefix))
        if filters.created_from:
            q = q.where(ApiKeyOrmModel.created >= day_start_utc(filters.created_from, zone))
        if filters.created_to:
            q = q.where(ApiKeyOrmModel.created < day_after_utc(filters.created_to, zone))
        if filters.expiry == "never":
            q = q.where(ApiKeyOrmModel.expires_at.is_(None))
        elif filters.expiry == "expired":
            q = q.where(ApiKeyOrmModel.expires_at <= now_utc())
        elif filters.expiry == "active":
            q = q.where(ApiKeyOrmModel.expires_at > now_utc())
        elif filters.expiry == "unexpired":
            q = q.where(
                or_(ApiKeyOrmModel.expires_at.is_(None), ApiKeyOrmModel.expires_at > now_utc())
            )
        if filters.kind is not None:
            q = q.where(_holds_terminal_grant(filters.kind == "terminal"))

        _sort_column_map = {
            "id": ApiKeyOrmModel.id,
            "name": ApiKeyOrmModel.name,
            "created": ApiKeyOrmModel.created,
            "expires_at": ApiKeyOrmModel.expires_at,
        }
        # Without an `order_by` the list sorts by `id desc`, newest first.
        sort_col = _sort_column_map.get(filters.order_by or "id", ApiKeyOrmModel.id)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
        )
        return total, [_orm_to_entity(o) for o in rows]

    async def save(self, key: ApiKey) -> ApiKey:
        """Flushes without committing; the calling use case commits, so a key
        is created atomically with its backing service-user row."""
        if key.id == 0:
            orm = ApiKeyOrmModel(**_entity_to_orm_dict(key))
            self._db.add(orm)
            await self._db.flush()
            return _orm_to_entity(orm)
        existing = await self._db.scalar(
            select(ApiKeyOrmModel).where(ApiKeyOrmModel.id == key.id).limit(1)
        )
        if not existing:
            raise ValueError(f"ApiKeyOrmModel id={key.id} not found.")
        orm = existing
        for k, v in _entity_to_orm_dict(key).items():
            setattr(orm, k, v)
        await self._db.flush()
        return _orm_to_entity(orm)
