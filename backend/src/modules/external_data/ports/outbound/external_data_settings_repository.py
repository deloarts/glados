"""
The settings sections CAD & external data owns: the PDM vault connection and
its sync state, the EPLAN Data Portal and the stock service.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings


@runtime_checkable
class IExternalDataSettingsRepository(ICatalogueSettingsRepository, Protocol):
    # ── PDM ───────────────────────────────────────────────────────────

    async def get_pdm(self) -> AdminPdmSettings: ...

    async def save_pdm(self, settings: AdminPdmSettings) -> AdminPdmSettings: ...

    async def save_pdm_session(
        self, *, token: str | None, user_id: int | None, obtained_at: datetime | None
    ) -> None:
        """Updates only session_token/session_user_id/session_obtained_at,
        no audit entry: called by PdmSessionService on every
        (re-)authenticate and on session clear, not by an admin action."""
        ...

    async def save_pdm_poll_status(
        self, *, at: datetime | None, error: str | None, summary: str | None
    ) -> None:
        """Updates only last_poll_at/last_poll_error/last_poll_summary, no
        audit entry: called by the poller after every tick and by
        RequestPdmPoll to force the next RunPdmPollIfDue check."""
        ...

    async def save_pdm_vault_id(self, vault_id: str) -> None:
        """Updates only the cached vault GUID, no audit entry: called by
        the poller once vault_info() has resolved it."""
        ...

    async def save_pdm_reconcile_requested(self, deep: bool | None) -> None:
        """Updates only reconcile_requested_deep, no audit entry: called by
        RequestPdmReconciliation to queue a run and by RunPdmPollIfDue to
        clear it back to None once consumed, whether the run succeeded or
        not."""
        ...

    # ── EPLAN Data Portal ─────────────────────────────────────────────

    async def get_edp(self) -> AdminEdpSettings: ...

    async def save_edp(self, settings: AdminEdpSettings) -> AdminEdpSettings: ...

    # ── Stock service ─────────────────────────────────────────────────

    async def get_stock(self) -> AdminStockSettings: ...

    async def save_stock(self, settings: AdminStockSettings) -> AdminStockSettings: ...
