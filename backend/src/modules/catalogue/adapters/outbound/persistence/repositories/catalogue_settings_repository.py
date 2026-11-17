"""
SQLAlchemy implementation of the settings sections Catalogue owns: orders,
made items and the spreadsheet import profiles.
"""

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.data_import import (
    AdminDataImportSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.made_items import (
    AdminMadeItemSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    data_import,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    made_items,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    orders,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import AdminDataImportSettings
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SINGLETON_ID,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SqlAlchemyPlatformSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    upsert_singleton,
)


class SqlAlchemyCatalogueSettingsRepository(
    SqlAlchemyPlatformSettingsRepository, ICatalogueSettingsRepository
):
    # ── Orders ────────────────────────────────────────────────────────

    async def get_orders(self) -> AdminOrderSettings:
        orm = await self._db.get(AdminOrderSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin bought item settings not seeded, run InitDatabase first.")
        return orders.to_entity(orm)

    async def save_orders(self, s: AdminOrderSettings) -> AdminOrderSettings:
        orm = await upsert_singleton(self._db, AdminOrderSettingsOrmModel, orders.to_dict(s))
        return orders.to_entity(orm)

    # ── Made items ────────────────────────────────────────────────────

    async def get_made_items(self) -> AdminMadeItemSettings:
        orm = await self._db.get(AdminMadeItemSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin made item settings not seeded, run InitDatabase first.")
        return made_items.to_entity(orm)

    async def save_made_items(self, s: AdminMadeItemSettings) -> AdminMadeItemSettings:
        orm = await upsert_singleton(self._db, AdminMadeItemSettingsOrmModel, made_items.to_dict(s))
        return made_items.to_entity(orm)

    # ── Data import ───────────────────────────────────────────────────

    async def get_data_import(self) -> AdminDataImportSettings:
        """Startup seeds the row. A database without it reads as no stored
        profile, so every import falls back to its empty default profile
        instead of failing."""
        orm = await self._db.get(AdminDataImportSettingsOrmModel, SINGLETON_ID)
        if not orm:
            return data_import.empty_defaults()
        return data_import.to_entity(orm)

    async def save_data_import(self, s: AdminDataImportSettings) -> AdminDataImportSettings:
        orm = await upsert_singleton(
            self._db, AdminDataImportSettingsOrmModel, data_import.to_dict(s)
        )
        return data_import.to_entity(orm)
