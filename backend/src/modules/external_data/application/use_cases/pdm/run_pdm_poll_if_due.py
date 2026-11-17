"""The gate the PDM poll scheduler calls every 60 seconds. Cheap checks come
first and the advisory lock only once a poll is about to run, so most ticks
on most workers end after one settings read.

A queued reconciliation runs first, independent of the poll interval, and
its flag is cleared on success and failure alike so an error can never
wedge it. A manual poll is signalled by clearing `last_poll_at`, which a
never-polled vault also has, so the run log decides between a manual and
an initial run.
"""

from datetime import timedelta

from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollPdmVault
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollSummary
from src.modules.external_data.application.use_cases.pdm.reconcile_pdm_vault import (
    ReconcilePdmVault,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_poll_lock_port import IPdmPollLock
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class RunPdmPollIfDue:
    def __init__(
        self,
        admin_settings_repo: IExternalDataSettingsRepository,
        lock: IPdmPollLock,
        poll: PollPdmVault,
        reconcile: ReconcilePdmVault,
        run_repo: IPdmSyncRunRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._uow = uow
        self._admin_settings = admin_settings_repo
        self._lock = lock
        self._poll = poll
        self._reconcile = reconcile
        self._runs = run_repo

    async def execute(self) -> PollSummary | None:
        """Returns the poll summary, or None when no poll ran. Reconciliation
        and polling take the shared tick lock separately."""
        settings = await self._admin_settings.get_pdm()
        if is_pdm_enabled(settings) and settings.reconcile_requested_deep is not None:
            await self._run_reconciliation(settings.reconcile_requested_deep)
            settings = await self._admin_settings.get_pdm()

        if not is_pdm_enabled(settings):
            return None
        if not self._is_due(settings):
            return None

        trigger = await self._resolve_trigger(settings)

        async with self._lock.lock() as locked:
            if not locked:
                log.debug("PDM poll: another worker holds the tick lock, skipping.")
                return None
            return await self._poll.execute(trigger=trigger)

    async def _resolve_trigger(self, settings: AdminPdmSettings) -> PdmSyncTrigger:
        """SCHEDULED while `last_poll_at` is set; otherwise INITIAL if no
        scheduled or manual run was ever recorded, else MANUAL."""
        if settings.last_poll_at is not None:
            return PdmSyncTrigger.SCHEDULED
        ever_polled = (
            await self._runs.latest_by_trigger(PdmSyncTrigger.SCHEDULED.value) is not None
            or await self._runs.latest_by_trigger(PdmSyncTrigger.MANUAL.value) is not None
        )
        return PdmSyncTrigger.MANUAL if ever_polled else PdmSyncTrigger.INITIAL

    async def _run_reconciliation(self, deep: bool) -> None:
        async with self._lock.lock() as locked:
            if not locked:
                log.debug(
                    "PDM reconciliation: another worker holds the tick lock, skipping this tick."
                )
                return
            try:
                await self._reconcile.execute(deep=deep)
            except Exception:
                log.exception("PDM reconciliation: requested run failed.")
            finally:
                await self._admin_settings.save_pdm_reconcile_requested(None)
                await self._uow.commit()

    @staticmethod
    def _is_due(settings: AdminPdmSettings) -> bool:
        if settings.last_poll_at is None:
            return True
        elapsed = now_utc() - settings.last_poll_at
        return elapsed >= timedelta(minutes=settings.poll_interval_minutes)
