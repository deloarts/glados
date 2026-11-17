"""
Backs the admin "View sync log" dialog's entries list (GET
/admin/settings/pdm/runs/{run_id}/entries): a paged, optionally
action-filtered read of one run's per-file entries, shown on selecting a
row in the runs list. Read-only, no call to the vault.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmSyncRunEntryResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.domain.errors import AdminSettingsNotFoundError
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class ListPdmSyncRunEntries:
    def __init__(self, repo: IPdmSyncRunRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        actor: User,
        run_id: int,
        skip: int | None,
        limit: int | None,
        action: str | None,
        search: str | None = None,
        kind: str | None = None,
    ) -> tuple[int, list[PdmSyncRunEntryResult]]:
        SettingsRules.assert_can_read(actor)

        if await self._repo.get_by_id(run_id) is None:
            raise AdminSettingsNotFoundError(f"PDM sync run #{run_id} not found.")

        total, rows = await self._repo.get_entries(run_id, skip, limit, action, search, kind)
        return total, [PdmVaultMapper.pdm_sync_run_entry_to_result(r) for r in rows]
