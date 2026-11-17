"""
The settings section Planning & fulfillment owns: production.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.api import ICatalogueSettingsRepository
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)


@runtime_checkable
class IFulfillmentSettingsRepository(ICatalogueSettingsRepository, Protocol):
    # ── Production ────────────────────────────────────────────────────

    async def get_production(self) -> AdminProductionSettings: ...

    async def save_production(
        self, settings: AdminProductionSettings
    ) -> AdminProductionSettings: ...
