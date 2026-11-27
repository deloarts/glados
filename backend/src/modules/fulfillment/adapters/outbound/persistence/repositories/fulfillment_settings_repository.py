"""
SQLAlchemy implementation of the settings sections Planning & fulfillment
owns: production and planning.
"""

from src.modules.catalogue.adapters.outbound.persistence.repositories.catalogue_settings_repository import (
    SqlAlchemyCatalogueSettingsRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.planning import (
    AdminPlanningSettingsOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    planning,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    production,
)
from src.modules.fulfillment.domain.entities.admin_settings.planning import AdminPlanningSettings
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SINGLETON_ID,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    upsert_singleton,
)


class SqlAlchemyFulfillmentSettingsRepository(
    SqlAlchemyCatalogueSettingsRepository, IFulfillmentSettingsRepository
):
    # ── Production ────────────────────────────────────────────────────

    async def get_production(self) -> AdminProductionSettings:
        orm = await self._db.get(AdminProductionSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin production settings not seeded, run InitDatabase first.")
        return production.to_entity(orm)

    async def save_production(self, s: AdminProductionSettings) -> AdminProductionSettings:
        orm = await upsert_singleton(
            self._db, AdminProductionSettingsOrmModel, production.to_dict(s)
        )
        return production.to_entity(orm)

    # ── Planning ──────────────────────────────────────────────────────

    async def get_planning(self) -> AdminPlanningSettings:
        orm = await self._db.get(AdminPlanningSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin planning settings not seeded, run InitDatabase first.")
        return planning.to_entity(orm)

    async def save_planning(self, s: AdminPlanningSettings) -> AdminPlanningSettings:
        orm = await upsert_singleton(self._db, AdminPlanningSettingsOrmModel, planning.to_dict(s))
        return planning.to_entity(orm)
