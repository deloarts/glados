"""
Backs the admin sync log dialog's runs list (GET
/admin/settings/pdm/runs): a paged, newest-first read of the PDM sync run
log PollPdmVault and RefreshPdmFile write. Read-only, no call to the vault.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmSyncRunResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    PdmSyncRunFilterDto,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class ListPdmSyncRuns:
    def __init__(self, repo: IPdmSyncRunRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        actor: User,
        skip: int | None,
        limit: int | None,
        filters: PdmSyncRunFilterDto | None = None,
    ) -> tuple[int, list[PdmSyncRunResult]]:
        SettingsRules.assert_can_read(actor)

        total, rows = await self._repo.get_multi(skip, limit, filters)
        return total, [PdmVaultMapper.pdm_sync_run_to_result(r) for r in rows]
