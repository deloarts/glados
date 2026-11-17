"""Update authentication and session security settings (TOTP enforcement, login
methods, password length, lockout) and audit the change."""

from src.modules.platform.application.dto.admin_settings_dto.security import (
    AdminSecuritySettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.security import (
    UpdateSecuritySettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.security import (
    SecuritySettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateSecuritySettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateSecuritySettingsCommand
    ) -> AdminSecuritySettingsResult:
        SettingsRules.assert_can_write(actor)

        if cmd.min_password_length < 1:
            raise ValueError("Minimum password length must be at least 1.")

        settings = AdminSecuritySettings(
            id=1,
            enforce_totp=cmd.enforce_totp,
            allow_rfid_login=cmd.allow_rfid_login,
            allow_local_login=cmd.allow_local_login,
            enable_api_key_auth=cmd.enable_api_key_auth,
            min_password_length=cmd.min_password_length,
            session_timeout_minutes=cmd.session_timeout_minutes,
            totp_trusted_device_days=cmd.totp_trusted_device_days,
            max_login_attempts=cmd.max_login_attempts,
            lockout_duration_minutes=cmd.lockout_duration_minutes,
            token_max_lifetime_days=cmd.token_max_lifetime_days,
            session_max_lifetime_days=cmd.session_max_lifetime_days,
            enable_terminals=cmd.enable_terminals,
            enable_infoscreen_weather=cmd.enable_infoscreen_weather,
            terminal_allowed_ips=list(cmd.terminal_allowed_ips),
        )
        saved = await self._repo.save_security(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="security",
                summary=f"Security settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated security settings.")
        return SecuritySettingsMapper.security_to_result(saved)
