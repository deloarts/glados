"""
Backs the settings page's reconciliation dialog run buttons (POST
/admin/settings/pdm/reconcile?deep=): sets reconcile_requested_deep so
RunPdmPollIfDue (checked every 60 seconds) runs ReconcilePdmVault on its
next tick, before and independent of the poll interval check. Does not run
the report itself and does not call the vault: accepted means "queued for
the next tick", not "done". Mirrors RequestPdmPoll's own shape.
"""

from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class RequestPdmReconciliation:
    def __init__(self, repo: IExternalDataSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, actor: User, deep: bool) -> None:
        SettingsRules.assert_can_write(actor)

        settings = await self._repo.get_pdm()
        if not is_pdm_enabled(settings):
            raise PdmNotEnabledError(
                "The PDM integration is not enabled and configured; there is nothing to reconcile."
            )

        await self._repo.save_pdm_reconcile_requested(deep)

        kind = "deep" if deep else "quick"
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="pdm",
                summary=f"PDM {kind} reconciliation requested by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info(f"Requested a {kind} PDM reconciliation.")
