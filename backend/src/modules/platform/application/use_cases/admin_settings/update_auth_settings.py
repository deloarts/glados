"""
Authentication provider configuration.

Unlike mail and storage, this domain has **no secret field** and therefore no
"None means keep existing" handling: LDAP authentication binds directly as the
end user, so no service-account credential is ever stored. If you find yourself
adding a `*_configured` flag here, check that assumption first.
"""

from src.modules.platform.application.dto.admin_settings_dto.auth import AdminAuthSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.auth import UpdateAuthSettingsCommand
from src.modules.platform.application.mappers.admin_settings_mapper.auth import AuthSettingsMapper
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateAuthSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, actor: User, cmd: UpdateAuthSettingsCommand) -> AdminAuthSettingsResult:
        SettingsRules.assert_can_write(actor)

        # Range validation lives on the command (Field constraints), so it
        # surfaces as a 422 at the schema boundary rather than an unmapped
        # ValueError, there is no ValueError handler, so a raise here would
        # become a 500.
        settings = AdminAuthSettings(
            id=1,
            ldap_enabled=cmd.ldap_enabled,
            ldap_host=cmd.ldap_host.strip(),
            ldap_port=cmd.ldap_port,
            ldap_use_ssl=cmd.ldap_use_ssl,
            ldap_start_tls=cmd.ldap_start_tls,
            ldap_verify_certificate=cmd.ldap_verify_certificate,
            ldap_domain=cmd.ldap_domain.strip(),
            ldap_timeout_seconds=cmd.ldap_timeout_seconds,
        )
        saved = await self._repo.save_auth(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="auth",
                summary=f"Auth settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated auth settings.")
        return AuthSettingsMapper.auth_to_result(saved)
