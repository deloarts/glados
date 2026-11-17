"""
Row mapping for the admin_stock_settings singleton. An API key no
configured key can decrypt loads as None, which reads as "not configured".
"""

from typing import Any

from src.modules.external_data.adapters.outbound.persistence.models.admin_settings_model.stock import (
    AdminStockSettingsOrmModel,
)
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings


def to_entity(o: AdminStockSettingsOrmModel) -> AdminStockSettings:
    return AdminStockSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        service_url=o.service_url,
        api_key=o.api_key or None,
    )


def to_dict(s: AdminStockSettings) -> dict[str, Any]:
    return {"enabled": s.enabled, "service_url": s.service_url, "api_key": s.api_key}


def disabled_defaults() -> AdminStockSettings:
    """What a database without the row reads as: switched off."""
    return AdminStockSettings(id=1)
