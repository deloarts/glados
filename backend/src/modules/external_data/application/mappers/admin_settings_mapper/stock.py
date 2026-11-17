"""
Maps the stock service settings entity to its result DTO. The API key never
leaves the server; the result only says whether one is stored.
"""

from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    AdminStockSettingsResult,
)
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings


class StockSettingsMapper:
    @staticmethod
    def stock_to_result(e: AdminStockSettings) -> AdminStockSettingsResult:
        return AdminStockSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            service_url=e.service_url,
            api_key_configured=bool(e.api_key),
            is_configured=e.is_configured,
            is_ready=e.is_ready,
        )
