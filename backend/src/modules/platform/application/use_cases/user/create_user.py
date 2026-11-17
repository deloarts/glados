"""
Orchestrates user creation:
  1. Check actor has permission
  2. Validate uniqueness (username, email, rfid)
  3. Hash the password (directory accounts get an unusable sentinel) and
     index the rfid
  4. Persist via repository, record it in the security log, and commit
  5. Fire welcome email (non-fatal)
  6. Return result DTO
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.application.dto.user_dto import CreateUserCommand
from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.services.user_group_membership import validated_group_ids
from src.modules.platform.const import SERVER_DEFAULT_BUTTON_FLAT_STYLE
from src.modules.platform.const import SERVER_DEFAULT_TABLE_GRIDLINES
from src.modules.platform.const import SERVER_DEFAULT_TABLE_STRIPED_ROWS
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import EmailAlreadyExistsError
from src.modules.platform.domain.exceptions import RfidAlreadyExistsError
from src.modules.platform.domain.exceptions import UsernameAlreadyExistsError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.hashing import unusable_password_hash
from src.modules.platform.infrastructure.security.rfid import rfid_lookup
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class CreateUser:
    def __init__(
        self,
        user_repo: IUserRepository,
        mail_service: IMailService,
        hash_fn: Callable[[str], Awaitable[str]],
        settings_repo: IPlatformSettingsRepository,
        *,
        uow: IUnitOfWork,
        group_repo: IUserGroupRepository | None = None,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._mail = mail_service
        self._hash = hash_fn
        self._settings = settings_repo
        self._uow = uow
        self._groups = group_repo
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, cmd: CreateUserCommand) -> UserResult:
        # 1. Permission check
        UserRules.assert_can_create(actor)
        UserRules.assert_permissions_assignable(None, list(cmd.permissions))
        # There is exactly one system account, the `system` row that
        # init_db creates and re-syncs. CreateUserCommand carries no
        # is_systemuser field (nor does UserCreateRequest), and
        # the entity below is built with the flag hard-wired to False, so
        # no actor, the system user included, can mint another one.

        # 2. Uniqueness checks
        UserRules.assert_username_not_reserved(cmd.username)
        if await self._repo.get_by_username(cmd.username):
            raise UsernameAlreadyExistsError(
                f"A user with username {cmd.username!r} already exists."
            )
        if await self._repo.get_by_email(cmd.email):
            raise EmailAlreadyExistsError(f"A user with email {cmd.email!r} already exists.")
        if cmd.rfid and await self._repo.get_by_rfid(cmd.rfid):
            raise RfidAlreadyExistsError("The given RFID is already assigned to an account.")

        # 3. Hash credentials. A directory account gets a hash nothing can
        # match: the directory is the only authority for it, so there is no
        # local password to store and none to guess.
        if cmd.auth_provider == AuthProvider.LDAP:
            hashed_password = unusable_password_hash()
        else:
            hashed_password = await self._hash(UserRules.require_password(cmd.password))
        rfid_lookup_value = rfid_lookup(cmd.rfid) if cmd.rfid else None

        # Locale fallbacks come from the admin-configured tenant defaults
        # (Locales section, General tab), not the const.py constants: those
        # are only the column server_default values, see
        # AdminGeneralSettings.default_language.
        general = await self._settings.get_general()

        # 3b. Validate shared-account members (meaningless, and forced empty, otherwise)
        member_ids: list[int] = []
        if cmd.is_shared_account:
            for member_id in cmd.member_ids:
                candidate = await self._repo.get_by_id(member_id)
                UserRules.assert_valid_shared_account_member(target_id=None, candidate=candidate)
                member_ids.append(member_id)

        # 4. Build entity (id=0 → repo assigns the real id on save)
        user = User(
            id=0,
            username=cmd.username,
            full_name=cmd.full_name,
            email=cmd.email,
            created=now_utc(),
            hashed_password=hashed_password,
            rfid_lookup=rfid_lookup_value,
            is_active=cmd.is_active,
            is_systemuser=False,  # A0: unconditional, see the assert above
            is_shared_account=cmd.is_shared_account,
            auth_provider=cmd.auth_provider,
            member_ids=member_ids,
            permissions=list(cmd.permissions),
            language=cmd.language or general.default_language,
            date_format=cmd.date_format or general.default_date_format,
            # No tenant-wide default to fall back to (DECISION: per-user
            # only, see StartPage's docstring), unlike the two fields
            # above.
            start_page=cmd.start_page or StartPage.default(),
            theme_preset=cmd.theme_preset or ThemePreset.default(),
            theme_surface=cmd.theme_surface or ThemeSurface.default(),
            theme_primary=cmd.theme_primary or ThemePrimary.default(),
            theme_dark_mode=cmd.theme_dark_mode if cmd.theme_dark_mode is not None else True,
            button_flat_style=(
                cmd.button_flat_style
                if cmd.button_flat_style is not None
                else SERVER_DEFAULT_BUTTON_FLAT_STYLE
            ),
            table_gridlines=(
                cmd.table_gridlines
                if cmd.table_gridlines is not None
                else SERVER_DEFAULT_TABLE_GRIDLINES
            ),
            table_striped_rows=(
                cmd.table_striped_rows
                if cmd.table_striped_rows is not None
                else SERVER_DEFAULT_TABLE_STRIPED_ROWS
            ),
        )

        # A create payload carries no time tracking credentials; the rule
        # still runs so a payload that one day does cannot bypass it.
        UserRules.assert_time_tracking_credentials_allowed(user, has_credentials=False)
        user.group_ids = await validated_group_ids(self._groups, user, list(cmd.group_ids))

        # 5. Persist
        saved = await self._repo.save(user)
        await self._audit.record(
            SecurityEventType.USER_CREATED,
            actor=actor,
            target_user=saved,
            detail={
                "permissions": sorted(saved.permissions),
                "group_ids": sorted(saved.group_ids),
                "is_active": saved.is_active,
            },
        )
        await self._uow.commit()

        log.info(f"Created user {saved.username!r} (ID={saved.id}).")

        # 6. Welcome email, non-fatal: log on failure, don't propagate.
        # Never carries the password (see IMailService.send_welcome):
        # names the creator instead, so the new user asks them for it
        # out of band rather than it sitting in plaintext in an inbox.
        try:
            await self._mail.send_welcome(
                email=saved.email,
                full_name=saved.full_name,
                username=saved.username,
                created_by_name=actor.full_name,
                created_by_email=actor.email,
                language=saved.language,
            )
        except Exception as e:
            log.error(f"Welcome mail failed for {saved.email!r}: {e}")

        return UserMapper.to_result(saved)
