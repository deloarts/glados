"""
Loads and maps the user a row of any module refers to, such as the creator
of an order or the operator of a machine. Every repository that resolves a
related user uses these, so they sit next to the other persistence helpers
rather than inside the user repository.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption
from sqlalchemy.orm.strategy_options import _AbstractLoad

from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.shared_kernel.domain.services.clock import as_utc


@lru_cache(maxsize=1)
def user_load_options() -> tuple[ORMOption, ...]:
    """What user_orm_to_entity reads beyond columns. Every query that maps
    users loads it explicitly: relationships never load implicitly, and a
    user already in the session is only refreshed by an explicit option."""
    return (selectinload(UserOrmModel.members),)


def load_user(*path: Any) -> _AbstractLoad:
    """Selectin-loads the user at the end of the relationship `path`, which
    runs from the queried model to a user relationship, together with the
    memberships user_orm_to_entity reads. Every hop is a selectinload, so
    `load_user(A.b, B.creator)` is
    `selectinload(A.b).selectinload(B.creator).selectinload(UserOrmModel.members)`."""
    head, *rest = path
    loader = selectinload(head)
    for relationship in rest:
        loader = loader.selectinload(relationship)
    return loader.selectinload(UserOrmModel.members)


def user_orm_to_entity(orm: UserOrmModel) -> User:
    """Convert an ORM row to a domain entity. Reused by other repositories that
    need to resolve a related user (e.g. creator/orderer/receiver references)."""
    return User(
        id=orm.id,
        public_id=orm.public_id,
        username=orm.username,
        full_name=orm.full_name,
        email=orm.email,
        created=orm.created,
        hashed_password=orm.hashed_password,
        rfid_lookup=orm.rfid_lookup,
        token_version=orm.token_version,
        last_logged_in=orm.last_logged_in,
        # SQLite hands back naive datetimes; the passkey recheck compares
        # this against an aware now.
        password_verified_at=(
            as_utc(orm.password_verified_at) if orm.password_verified_at else None
        ),
        totp_secret=orm.totp_secret,
        totp_enabled=orm.totp_enabled,
        avatar_key=orm.avatar_key,
        is_active=orm.is_active,
        is_systemuser=orm.is_systemuser,
        is_service_account=orm.is_service_account,
        is_shared_account=orm.is_shared_account,
        auth_provider=orm.auth_provider,
        member_ids=[m.id for m in orm.members],
        permissions=list(orm.permissions or []),
        language=Language(orm.language),
        date_format=DateFormat(orm.date_format),
        start_page=StartPage(orm.start_page),
        theme_preset=ThemePreset(orm.theme_preset),
        theme_surface=ThemeSurface(orm.theme_surface),
        theme_primary=ThemePrimary(orm.theme_primary),
        theme_dark_mode=orm.theme_dark_mode,
        button_flat_style=orm.button_flat_style,
        table_gridlines=orm.table_gridlines,
        table_striped_rows=orm.table_striped_rows,
    )
