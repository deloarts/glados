"""
Backs the admin reconciliation dialog's own status read (GET
/admin/settings/pdm/reconciliation): the latest run with trigger
`reconciliation` (never a specific run id: a report never accumulates
across runs, see PdmReconciliationFinding's docstring) plus how many files
each category's findings stand for. `run` is None and `counts` is {} when
reconciliation has never run for this vault. Read-only, no call to the
vault.
"""

from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationReportResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.repositories.pdm_reconciliation_finding_repository import (
    IPdmReconciliationFindingRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetPdmReconciliation:
    def __init__(
        self, run_repo: IPdmSyncRunRepository, finding_repo: IPdmReconciliationFindingRepository
    ) -> None:
        self._runs = run_repo
        self._findings = finding_repo

    async def execute(self, actor: User) -> PdmReconciliationReportResult:
        SettingsRules.assert_can_read(actor)

        run = await self._runs.latest_by_trigger(PdmSyncTrigger.RECONCILIATION.value)
        if run is None:
            return PdmReconciliationReportResult(run=None, counts={})

        counts = await self._findings.counts_for_run(run.id)
        return PdmReconciliationReportResult(
            run=PdmVaultMapper.pdm_sync_run_to_result(run), counts=counts
        )
