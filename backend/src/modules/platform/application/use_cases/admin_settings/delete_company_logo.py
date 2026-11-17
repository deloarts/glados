"""
Clears the configured company logo from general admin settings and removes
the underlying storage object, recording an audit entry for the change.
"""

from dataclasses import replace

from src.modules.platform.application.dto.admin_settings_dto.general import (
    AdminGeneralSettingsResult,
)
from src.modules.platform.application.mappers.admin_settings_mapper.general import (
    GeneralSettingsMapper,
)
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class DeleteCompanyLogo:
    def __init__(
        self, repo: IPlatformSettingsRepository, storage: IStoragePort | None, *, uow: IUnitOfWork
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._storage = storage

    async def execute(self, actor: User) -> AdminGeneralSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_general()

        # Best-effort: clearing the reference is the part that matters, so a
        # storage hiccup must not leave the setting pointing at an image the
        # admin has already decided to remove.
        if current.company_logo_key and self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage, current.company_logo_key, context="removing company logo"
            )

        saved = await self._repo.save_general(replace(current, company_logo_key=None))

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="general",
                summary=f"Company logo removed by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Removed the company logo.")
        return GeneralSettingsMapper.general_to_result(saved)
