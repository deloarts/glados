"""
Backs the admin "Synchronize with PDM" button and its activity dialog (GET
/admin/settings/pdm/sync-activity): whether a synchronisation was requested
and is waiting for the scheduler, the poll run in progress, and the newest
processed files across every run. Read-only, no call to the vault.
"""

from datetime import timedelta

from src.modules.external_data.application.dto.pdm_dto import PdmSyncActivityResult
from src.modules.external_data.application.mappers.admin_settings_mapper.pdm_vault import (
    PdmVaultMapper,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.shared_kernel.domain.services.clock import now_utc

# Poll runs, as opposed to single-file refreshes and reconciliation reports.
_POLL_TRIGGERS = [
    PdmSyncTrigger.SCHEDULED.value,
    PdmSyncTrigger.MANUAL.value,
    PdmSyncTrigger.INITIAL.value,
]

# An unfinished run whose progress was not written for this long died
# mid-way; a live run writes it every few seconds.
_STALE_AFTER = timedelta(minutes=10)

_RECENT_ENTRIES = 10


class GetPdmSyncActivity:
    def __init__(
        self, settings_repo: IExternalDataSettingsRepository, run_repo: IPdmSyncRunRepository
    ) -> None:
        self._settings = settings_repo
        self._runs = run_repo

    async def execute(self, actor: User) -> PdmSyncActivityResult:
        SettingsRules.assert_can_read(actor)

        settings = await self._settings.get_pdm()
        run = await self._runs.latest_unfinished(_POLL_TRIGGERS)
        if run is not None and not _is_alive(run):
            run = None
        # RequestPdmPoll clears last_poll_at, so a cleared value with no run
        # in progress means the request waits for the next scheduler tick.
        requested = settings.enabled and settings.last_poll_at is None and run is None
        entries = await self._runs.recent_entries(_RECENT_ENTRIES)
        return PdmSyncActivityResult(
            requested=requested,
            run=PdmVaultMapper.pdm_sync_run_to_result(run) if run else None,
            recent_entries=[PdmVaultMapper.pdm_sync_run_entry_to_result(e) for e in entries],
        )


def _is_alive(run: PdmSyncRun) -> bool:
    heartbeat = run.progress_at or run.started_at
    return now_utc() - heartbeat < _STALE_AFTER
