"""
Backs the admin reconciliation dialog's findings table (GET
/admin/settings/pdm/reconciliation/findings): a paged, filtered read of
the latest reconciliation run's findings. Read-only, no call to the vault.
Returns an empty page (not an error) when reconciliation has never run,
matching GetPdmReconciliation's own "nothing yet" shape.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationFindingFilterDto
from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationFindingResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    IPdmReconciliationFindingRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    PdmReconciliationFindingFilterDto as PdmReconciliationFindingFilterPort,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class ListPdmReconciliationFindings:
    def __init__(
        self, run_repo: IPdmSyncRunRepository, finding_repo: IPdmReconciliationFindingRepository
    ) -> None:
        self._runs = run_repo
        self._findings = finding_repo

    async def execute(
        self, actor: User, filters: PdmReconciliationFindingFilterDto
    ) -> tuple[int, list[PdmReconciliationFindingResult]]:
        SettingsRules.assert_can_read(actor)

        run = await self._runs.latest_by_trigger(PdmSyncTrigger.RECONCILIATION.value)
        if run is None:
            return 0, []

        total, rows = await self._findings.get_multi(
            run.id,
            PdmReconciliationFindingFilterPort(
                skip=filters.skip,
                limit=filters.limit,
                category=filters.category,
                kind=filters.kind,
                search=filters.search,
                part_number=filters.part_number,
                message=filters.message,
            ),
        )
        return total, [PdmVaultMapper.pdm_reconciliation_finding_to_result(r) for r in rows]
