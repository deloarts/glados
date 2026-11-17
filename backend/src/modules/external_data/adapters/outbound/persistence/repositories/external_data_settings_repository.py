"""
SQLAlchemy implementation of the settings sections CAD & external data owns:
the PDM vault connection and its sync state, the EPLAN Data Portal and the
stock service.
"""

from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.catalogue_settings_repository import (
    SqlAlchemyCatalogueSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.eplan_data_portal import (
    AdminEdpSettingsOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.pdm import (
    AdminPdmSettingsOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.stock import (
    AdminStockSettingsOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    eplan_data_portal,
)
from src.modules.external_data.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    pdm,
)
from src.modules.external_data.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    stock,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SINGLETON_ID,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    upsert_singleton,
)


class SqlAlchemyExternalDataSettingsRepository(
    SqlAlchemyCatalogueSettingsRepository, IExternalDataSettingsRepository
):
    # ── PDM ───────────────────────────────────────────────────────────

    async def get_pdm(self) -> AdminPdmSettings:
        orm = await self._db.get(AdminPdmSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin PDM settings not seeded, run InitDatabase first.")
        return pdm.to_entity(orm)

    async def save_pdm(self, s: AdminPdmSettings) -> AdminPdmSettings:
        orm = await upsert_singleton(self._db, AdminPdmSettingsOrmModel, pdm.to_dict(s))
        return pdm.to_entity(orm)

    async def save_pdm_session(
        self, *, token: str | None, user_id: int | None, obtained_at: datetime | None
    ) -> None:
        """Updates the session columns without an audit entry, since this is
        not an admin action."""
        await upsert_singleton(
            self._db,
            AdminPdmSettingsOrmModel,
            {
                "session_token": token,
                "session_user_id": user_id,
                "session_obtained_at": obtained_at,
            },
        )

    async def save_pdm_poll_status(
        self, *, at: datetime | None, error: str | None, summary: str | None
    ) -> None:
        """Updates the poll status columns without an audit entry."""
        await upsert_singleton(
            self._db,
            AdminPdmSettingsOrmModel,
            {
                "last_poll_at": at,
                "last_poll_error": error,
                "last_poll_summary": summary,
            },
        )

    async def save_pdm_vault_id(self, vault_id: str) -> None:
        """Updates the cached vault GUID without an audit entry."""
        await upsert_singleton(self._db, AdminPdmSettingsOrmModel, {"vault_id": vault_id})

    async def save_pdm_reconcile_requested(self, deep: bool | None) -> None:
        """Updates reconcile_requested_deep without an audit entry."""
        await upsert_singleton(
            self._db, AdminPdmSettingsOrmModel, {"reconcile_requested_deep": deep}
        )

    # ── EPLAN Data Portal ─────────────────────────────────────────────

    async def get_edp(self) -> AdminEdpSettings:
        """Startup seeds the row. A database without it reads as switched
        off, the safe default."""
        orm = await self._db.get(AdminEdpSettingsOrmModel, SINGLETON_ID)
        if not orm:
            return eplan_data_portal.disabled_defaults()
        return eplan_data_portal.to_entity(orm)

    async def save_edp(self, s: AdminEdpSettings) -> AdminEdpSettings:
        orm = await upsert_singleton(
            self._db, AdminEdpSettingsOrmModel, eplan_data_portal.to_dict(s)
        )
        return eplan_data_portal.to_entity(orm)

    # ── Stock service ─────────────────────────────────────────────────

    async def get_stock(self) -> AdminStockSettings:
        """Startup seeds the row. A database without it reads as switched
        off, the safe default."""
        orm = await self._db.get(AdminStockSettingsOrmModel, SINGLETON_ID)
        if not orm:
            return stock.disabled_defaults()
        return stock.to_entity(orm)

    async def save_stock(self, s: AdminStockSettings) -> AdminStockSettings:
        orm = await upsert_singleton(self._db, AdminStockSettingsOrmModel, stock.to_dict(s))
        return stock.to_entity(orm)
