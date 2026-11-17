"""Deletes every user's stored time tracking credentials, for incidents and
for switching time tracking off for good. Disabling time tracking alone keeps
them, so re-enabling works without every user entering them again. The
audit entry records only how many were removed."""

from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    PurgeTimeTrackingCredentialsResult,
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
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class PurgeTimeTrackingCredentials:
    def __init__(
        self,
        repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = repo
        self._credentials = credentials_repo
        self._uow = uow

    async def execute(self, actor: User) -> PurgeTimeTrackingCredentialsResult:
        SettingsRules.assert_can_write(actor)

        deleted = await self._credentials.delete_all()
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="time_tracking",
                summary=(
                    f"All stored time tracking credentials deleted by {actor.username} "
                    f"({deleted} removed)."
                ),
            )
        )
        await self._uow.commit()

        log.warning("Deleted all stored time tracking credentials (%s removed).", deleted)
        return PurgeTimeTrackingCredentialsResult(deleted=deleted)
