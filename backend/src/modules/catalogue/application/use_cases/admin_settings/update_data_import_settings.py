"""Updates the import profiles of the data import settings. Each listed
profile replaces the stored one of its import type after
data_import_profiles.validate_profile() has checked and cleaned it; import
types the command does not list keep their stored profile. The audit entry
names the import types that changed."""

from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    AdminDataImportSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    UpdateDataImportSettingsCommand,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.data_import import (
    DataImportSettingsMapper,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import AdminDataImportSettings
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.errors import DataImportSettingsInvalidError
from src.modules.catalogue.domain.services.data_import_profiles import validate_profile
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateDataImportSettings:
    def __init__(self, repo: ICatalogueSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateDataImportSettingsCommand
    ) -> AdminDataImportSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_data_import()
        profiles = {t.value: current.profile(t) for t in DataImportType}
        changed: list[str] = []
        for item in cmd.profiles:
            if item.import_type not in DataImportType.values():
                raise DataImportSettingsInvalidError(f"Unknown import type {item.import_type!r}.")
            import_type = DataImportType(item.import_type)
            profile = validate_profile(
                import_type,
                DataImportProfile(
                    header_row=item.header_row,
                    data_offset=item.data_offset,
                    max_rows=item.max_rows,
                    column_names=item.column_names,
                ),
            )
            if profile != profiles[import_type.value]:
                changed.append(import_type.value)
            profiles[import_type.value] = profile

        saved = await self._repo.save_data_import(
            AdminDataImportSettings(id=1, public_id=current.public_id, profiles=profiles)
        )
        if changed:
            await self._repo.append_audit(
                AdminSettingsAuditEntry.by_actor(
                    actor,
                    settings_domain="data_import",
                    summary=(
                        f"Data import profiles {', '.join(changed)} updated by {actor.username}."
                    ),
                )
            )
        await self._uow.commit()

        log.info("Updated data import settings.")
        return DataImportSettingsMapper.data_import_to_result(saved)
