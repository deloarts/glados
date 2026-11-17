"""
Issues an API key: the shared step of the admin API key route and of the
terminal keys Operations issues. Both are recorded in the security log, a
terminal key as such, in the transaction that creates the key.
"""

import secrets
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime

from src.modules.platform.application.dto.api_key_dto import CreatedApiKeyResult
from src.modules.platform.application.mappers.api_key_mapper import ApiKeyMapper
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.const import SERVER_DEFAULT_BUTTON_FLAT_STYLE
from src.modules.platform.const import SERVER_DEFAULT_DATE_FORMAT
from src.modules.platform.const import SERVER_DEFAULT_LANGUAGE
from src.modules.platform.const import SERVER_DEFAULT_START_PAGE
from src.modules.platform.const import SERVER_DEFAULT_TABLE_GRIDLINES
from src.modules.platform.const import SERVER_DEFAULT_TABLE_STRIPED_ROWS
from src.modules.platform.const import SERVER_DEFAULT_THEME_DARK_MODE
from src.modules.platform.const import SERVER_DEFAULT_THEME_PRESET
from src.modules.platform.const import SERVER_DEFAULT_THEME_PRIMARY
from src.modules.platform.const import SERVER_DEFAULT_THEME_SURFACE
from src.modules.platform.domain.entities.api_key import ApiKey
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.api_key import display_prefix
from src.modules.platform.infrastructure.security.api_key import generate_api_key
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


async def issue_api_key(
    key_repo: IApiKeyRepository,
    user_repo: IUserRepository,
    uow: IUnitOfWork,
    hash_password: Callable[[str], Awaitable[str]],
    *,
    actor: User,
    name: str,
    permissions: list[str],
    expires_at: datetime | None,
    now: datetime,
    audit: SecurityAudit | None = None,
) -> CreatedApiKeyResult:
    """Creates the backing service account and the key in one transaction
    and commits it. The caller has already checked who may create the key
    and which permissions it may carry."""
    raw_token = generate_api_key()
    suffix = secrets.token_hex(4)

    service_user = User(
        id=0,
        username=f"apikey-{suffix}",
        full_name=f"API Key: {name}",
        email=f"apikey+{suffix}@service.invalid",
        created=now,
        hashed_password=await hash_password(secrets.token_urlsafe(32)),
        is_active=True,
        is_systemuser=False,
        is_service_account=True,
        permissions=list(permissions),
        # Deliberately the shipped SERVER_DEFAULT_* constants, not the
        # admin-configured `general` settings domain defaults CreateUser
        # reads: an API key's backing service user never renders a
        # UI, so there is no login screen or account page for a locale
        # setting to affect.
        language=Language(SERVER_DEFAULT_LANGUAGE),
        date_format=DateFormat(SERVER_DEFAULT_DATE_FORMAT),
        # Same reasoning as date_format above: a service account never
        # signs in through the UI, so there is no post-login landing
        # page to route it to.
        start_page=StartPage(SERVER_DEFAULT_START_PAGE),
        theme_preset=ThemePreset(SERVER_DEFAULT_THEME_PRESET),
        theme_surface=ThemeSurface(SERVER_DEFAULT_THEME_SURFACE),
        theme_primary=ThemePrimary(SERVER_DEFAULT_THEME_PRIMARY),
        theme_dark_mode=SERVER_DEFAULT_THEME_DARK_MODE,
        button_flat_style=SERVER_DEFAULT_BUTTON_FLAT_STYLE,
        table_gridlines=SERVER_DEFAULT_TABLE_GRIDLINES,
        table_striped_rows=SERVER_DEFAULT_TABLE_STRIPED_ROWS,
    )
    # A service account never holds time tracking credentials; the rule
    # still runs so a payload that one day carries them cannot bypass it.
    UserRules.assert_time_tracking_credentials_allowed(service_user, has_credentials=False)
    saved_user = await user_repo.save(service_user)

    key = ApiKey(
        id=0,
        name=name,
        token_hash=hash_api_key(raw_token),
        token_prefix=display_prefix(raw_token),
        user_id=saved_user.id,
        permissions=list(permissions),
        created_by_id=actor.id,
        created=now,
        expires_at=expires_at,
        revoked_at=None,
    )
    saved_key = await key_repo.save(key)
    await (audit or SecurityAudit.disabled()).record(
        api_key_event(saved_key, created=True),
        actor=actor,
        target_user=saved_user,
        target_id=saved_key.id,
        detail={
            "name": saved_key.name,
            "permissions": saved_key.permissions,
            "expires_at": saved_key.expires_at.isoformat() if saved_key.expires_at else None,
        },
    )

    await uow.commit()

    log.info(
        f"Created API key {saved_key.name!r} (ID={saved_key.id}, service user ID={saved_user.id})."
    )

    return ApiKeyMapper.to_created_result(saved_key, raw_token)


def api_key_event(key: ApiKey, *, created: bool) -> SecurityEventType:
    """The security event type of creating or revoking `key`, which tells a
    terminal key from any other API key."""
    if key.is_terminal_key:
        return (
            SecurityEventType.TERMINAL_KEY_CREATED
            if created
            else SecurityEventType.TERMINAL_KEY_REVOKED
        )
    return SecurityEventType.API_KEY_CREATED if created else SecurityEventType.API_KEY_REVOKED
