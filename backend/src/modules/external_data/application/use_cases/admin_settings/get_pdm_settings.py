"""
Routes GET /admin/settings/pdm through the use-case layer, matching
the module's other GETs (see get_made_item_settings.py's docstring).

Also folds in the poller's snapshot summary (snapshot_counts): the PDM
settings page is the one place that reads it, so it is resolved here
rather than added to every caller of PdmSettingsMapper.pdm_to_result
(see that method's docstring). Empty when no vault_id has been resolved
yet, there is nothing to count against.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm import AdminPdmSettingsResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm import (
    PdmSettingsMapper,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetPdmSettings:
    def __init__(
        self,
        repo: IExternalDataSettingsRepository,
        snapshot_repo: IPdmFileSnapshotRepository,
        *,
        mutating_operations_enabled: bool = False,
    ) -> None:
        self._repo = repo
        self._snapshot_repo = snapshot_repo
        self._mutating_operations_enabled = mutating_operations_enabled

    async def execute(self, actor: User) -> AdminPdmSettingsResult:
        SettingsRules.assert_can_read(actor)
        settings = await self._repo.get_pdm()
        snapshot_counts = (
            await self._snapshot_repo.counts_by_state(settings.vault_id)
            if settings.vault_id
            else {}
        )
        return PdmSettingsMapper.pdm_to_result(
            settings,
            snapshot_counts=snapshot_counts,
            mutating_operations_enabled=self._mutating_operations_enabled,
        )
