"""
The settings sections Catalogue owns: the order section (bought item numbering,
the PDM part number pattern and the delivery tolerances, next to the order and
quote request numbering), made items and the spreadsheet import profiles.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.admin_settings.data_import import AdminDataImportSettings
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.platform.api import IPlatformSettingsRepository


@runtime_checkable
class ICatalogueSettingsRepository(IPlatformSettingsRepository, Protocol):
    # ── Orders ────────────────────────────────────────────────────────

    async def get_orders(self) -> AdminOrderSettings: ...

    async def save_orders(self, settings: AdminOrderSettings) -> AdminOrderSettings: ...

    # ── Made items ────────────────────────────────────────────────────

    async def get_made_items(self) -> AdminMadeItemSettings: ...

    async def save_made_items(self, settings: AdminMadeItemSettings) -> AdminMadeItemSettings: ...

    # ── Data import ───────────────────────────────────────────────────

    async def get_data_import(self) -> AdminDataImportSettings: ...

    async def save_data_import(
        self, settings: AdminDataImportSettings
    ) -> AdminDataImportSettings: ...
