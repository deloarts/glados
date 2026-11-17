"""
Concrete implementation of IUserRepository using SQLAlchemy + Postgres.
Handles all ORM ↔ domain entity mapping via _to_entity (user_orm_to_entity
plus the groups) and _entity_to_orm_dict.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.models.user_group_model import (
    UserGroupOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import user_load_options
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.infrastructure.security.rfid import rfid_lookup
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto


def _entity_to_orm_dict(user: User) -> dict[str, Any]:
    """Convert a domain entity to a dict suitable for ORM construction/update."""
    return {
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "created": user.created,
        "hashed_password": user.hashed_password,
        "rfid_lookup": user.rfid_lookup,
        "token_version": user.token_version,
        "last_logged_in": user.last_logged_in,
        "password_verified_at": user.password_verified_at,
        "totp_secret": user.totp_secret,
        "totp_enabled": user.totp_enabled,
        "avatar_key": user.avatar_key,
        "is_active": user.is_active,
        "is_systemuser": user.is_systemuser,
        "is_service_account": user.is_service_account,
        "is_shared_account": user.is_shared_account,
        "auth_provider": user.auth_provider,
        "permissions": list(user.permissions),
        "language": user.language.value,
        "date_format": user.date_format.value,
        "start_page": user.start_page.value,
        "theme_preset": user.theme_preset.value,
        "theme_surface": user.theme_surface.value,
        "theme_primary": user.theme_primary.value,
        "theme_dark_mode": user.theme_dark_mode,
        "button_flat_style": user.button_flat_style,
        "table_gridlines": user.table_gridlines,
        "table_striped_rows": user.table_striped_rows,
    }


@lru_cache(maxsize=1)
def _user_options() -> tuple[ORMOption, ...]:
    """user_load_options plus the groups. Every other repository that maps a
    user leaves the groups unloaded, see User.group_ids; this one is the
    source of every user that is permission checked, so it always loads
    them."""
    return (*user_load_options(), selectinload(UserOrmModel.groups))


def _to_entity(orm: UserOrmModel) -> User:
    user = user_orm_to_entity(orm)
    user.group_ids = sorted(g.id for g in orm.groups)
    user.group_permissions = sorted({p for g in orm.groups for p in (g.permissions or [])})
    return user


class SqlAlchemyUserRepository(IUserRepository):
    """Implements IUserRepository using SQLAlchemy."""

    def __init__(self, db: AsyncSession) -> None:
        """Writes only flush and the caller's unit of work commits them."""
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> User | None:
        orm = await self._db.scalar(by_id(UserOrmModel, id, *_user_options()).limit(1))
        return _to_entity(orm) if orm else None

    async def get_by_username(self, username: str) -> User | None:
        orm = await self._db.scalar(
            select(UserOrmModel)
            .options(*_user_options())
            .where(UserOrmModel.username == username)
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_by_email(self, email: str) -> User | None:
        orm = await self._db.scalar(
            select(UserOrmModel)
            .options(*_user_options())
            .where(UserOrmModel.email == email)
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_by_username_ci(self, username: str) -> User | None:
        value = username.strip().lower()
        if not value:
            return None
        orm = await self._db.scalar(
            select(UserOrmModel)
            .options(*_user_options())
            .where(func.lower(UserOrmModel.username) == value)
            .order_by(UserOrmModel.id)
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_by_email_ci(self, email: str) -> User | None:
        value = email.strip().lower()
        if not value:
            return None
        orm = await self._db.scalar(
            select(UserOrmModel)
            .options(*_user_options())
            .where(func.lower(UserOrmModel.email) == value)
            .order_by(UserOrmModel.id)
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        """Resolve a login identifier that may be a username or an e-mail.

        Case-insensitive on purpose: Active Directory's sAMAccountName is
        case-insensitive, so an exact match would reject a user whose
        directory login works as "Mock" before we ever reach the DC.

        Both columns are unique, so at most one row matches either predicate;
        only a case-variant collision (both `Alice` and `alice` exist, which
        Postgres' case-sensitive unique index permits) or one user's username
        equalling another's e-mail could return two. The ordering makes which
        one wins deterministic rather than dependent on the query plan.
        """
        value = identifier.strip().lower()
        if not value:
            return None
        orm = await self._db.scalar(
            select(UserOrmModel)
            .options(*_user_options())
            .where(
                or_(
                    func.lower(UserOrmModel.username) == value,
                    func.lower(UserOrmModel.email) == value,
                )
            )
            .order_by(UserOrmModel.id)
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_by_rfid(self, rfid: str) -> User | None:
        """Looks the tag up through the deterministic HMAC index (see
        infrastructure/security/rfid.py). A tag is found only once saving it
        wrote that index, there is no scan over the stored bcrypt hashes."""
        orm = await self._db.scalar(
            select(UserOrmModel)
            .options(*_user_options())
            .where(UserOrmModel.rfid_lookup == rfid_lookup(rfid), UserOrmModel.is_active.is_(True))
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]:
        q = select(UserOrmModel).options(*_user_options())

        if filters.id is not None:
            q = q.where(UserOrmModel.id == filters.id)
        if filters.is_active is not None:
            q = q.where(UserOrmModel.is_active.is_(filters.is_active))
        if filters.is_service_account is not None:
            q = q.where(UserOrmModel.is_service_account.is_(filters.is_service_account))
        if filters.username:
            q = q.where(contains_ci(UserOrmModel.username, filters.username))
        if filters.full_name:
            q = q.where(contains_ci(UserOrmModel.full_name, filters.full_name))
        if filters.email:
            q = q.where(contains_ci(UserOrmModel.email, filters.email))
        if filters.search:
            term = filters.search
            matches = contains_ci(UserOrmModel.username, term) | contains_ci(
                UserOrmModel.full_name, term
            )
            if filters.search_includes_email:
                matches = matches | contains_ci(UserOrmModel.email, term)
            q = q.where(matches)

        _sort_column_map = {
            "id": UserOrmModel.id,
            "username": UserOrmModel.username,
            "full_name": UserOrmModel.full_name,
            "email": UserOrmModel.email,
            "created": UserOrmModel.created,
        }
        # Without an `order_by` the list sorts by `id asc`, oldest first.
        sort_col = _sort_column_map.get(filters.order_by or "id", UserOrmModel.id)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="asc"),
        )
        return total, [_to_entity(o) for o in rows]

    # ── Mutations ─────────────────────────────────────────────────────

    async def _get_for_update(self, user_id: int) -> UserOrmModel | None:
        """The row with its members and groups loaded, since the update reassigns them."""
        return await self._db.get(
            UserOrmModel, user_id, options=list(_user_options()), populate_existing=True
        )

    async def _reload(self, user_id: int) -> UserOrmModel:
        """Re-reads the row with its members and groups after a write; populate_existing
        refreshes the instance already in the session."""
        return (
            await self._db.scalars(by_id(UserOrmModel, user_id, *_user_options(), refresh=True))
        ).one()

    async def _resolve_members(self, member_ids: list[int]) -> list[UserOrmModel]:
        if not member_ids:
            return []
        return await load_by_ids(self._db, UserOrmModel, member_ids)

    async def _resolve_groups(self, group_ids: list[int]) -> list[UserGroupOrmModel]:
        if not group_ids:
            return []
        return await load_by_ids(self._db, UserGroupOrmModel, group_ids)

    async def save(self, user: User) -> User:
        """Insert (id == 0) or update (id > 0). Flushes without committing."""
        if user.id == 0:
            # Members are assigned while the row is still new: assigning a
            # collection after the flush would make SQLAlchemy load the
            # (empty) old collection implicitly, which an AsyncSession
            # cannot do.
            orm = UserOrmModel(**_entity_to_orm_dict(user))
            orm.members = await self._resolve_members(user.member_ids)
            orm.groups = await self._resolve_groups(user.group_ids)
            self._db.add(orm)
            await self._db.flush()
            return _to_entity(await self._reload(orm.id))
        existing = await self._get_for_update(user.id)
        if not existing:
            raise ValueError(f"UserOrmModel with id={user.id} not found for update.")
        orm = existing
        for key, value in _entity_to_orm_dict(user).items():
            setattr(orm, key, value)
        orm.members = await self._resolve_members(user.member_ids)
        orm.groups = await self._resolve_groups(user.group_ids)
        await self._db.flush()
        return _to_entity(await self._reload(orm.id))

    async def delete(self, user: User) -> None:
        orm = await self._db.get(UserOrmModel, user.id)
        if not orm:
            raise UserNotFoundError(f"UserOrmModel with id={user.id} not found for deletion.")
        await self._db.delete(orm)
        await self._db.flush()
