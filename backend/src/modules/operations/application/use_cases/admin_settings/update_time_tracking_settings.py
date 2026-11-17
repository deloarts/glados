"""Updates the time tracking settings (see
docs/reference/time-tracking-credentials.md section 1).

Shape checks (URL form) are request validators; this use case enforces the
rule that needs the merged result: enabling only with a service URL and an
API key. A changed service URL clears the confirmed credential key, because
another service holds another key; time tracking stays unavailable to users
until the admin tests the new service and confirms its key. The audit entry
names an old and a new URL, and says when the API key changed, never what
it is.
"""

from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    AdminTimeTrackingSettingsResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    UpdateTimeTrackingSettingsCommand,
)
from src.modules.operations.application.mappers.admin_settings_mapper.time_tracking import (
    TimeTrackingSettingsMapper,
)
from src.modules.operations.application.use_cases.admin_settings.get_time_tracking_settings import (
    credential_holders,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _optional(value: str | None, current: str | None) -> str | None:
    """None keeps the stored value, an empty string clears it."""
    if value is None:
        return current
    return value or None


class UpdateTimeTrackingSettings:
    def __init__(
        self,
        repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        user_repo: IUserRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = repo
        self._credentials = credentials_repo
        self._users = user_repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateTimeTrackingSettingsCommand
    ) -> AdminTimeTrackingSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_time_tracking()
        service_url = cmd.service_url if cmd.service_url is not None else current.service_url
        url_changed = service_url != current.service_url
        api_key = (
            current.api_key
            if cmd.api_key is None
            else (cmd.api_key.get_secret_value().strip() or None)
        )
        settings = AdminTimeTrackingSettings(
            id=1,
            public_id=current.public_id,
            enabled=cmd.enabled if cmd.enabled is not None else current.enabled,
            service_url=service_url,
            api_key=api_key,
            credential_public_key=None if url_changed else current.credential_public_key,
            credential_key_id=None if url_changed else current.credential_key_id,
            provider_label=None if url_changed else current.provider_label,
            privacy_policy_url=_optional(cmd.privacy_policy_url, current.privacy_policy_url),
        )
        settings.assert_valid()

        saved = await self._repo.save_time_tracking(settings)
        changes: list[str] = []
        if url_changed:
            changes.append(
                f"service changed from {current.service_url or '(none)'} to "
                f"{saved.service_url or '(none)'}, credential key to be confirmed again"
            )
        if api_key != current.api_key:
            changes.append("API key changed")
        summary = f"Time tracking settings updated by {actor.username}"
        summary += f", {'; '.join(changes)}." if changes else "."
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor, settings_domain="time_tracking", summary=summary
            )
        )
        await self._uow.commit()

        log.info("Updated the time tracking settings.")
        return TimeTrackingSettingsMapper.time_tracking_to_result(
            saved,
            credential_holders=await credential_holders(saved, self._credentials, self._users),
        )
