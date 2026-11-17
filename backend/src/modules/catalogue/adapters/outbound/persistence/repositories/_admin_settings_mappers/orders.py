"""
Row mapping for the admin_order_settings singleton. Converts the ORM row to the
domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.orders import (
    AdminOrderSettingsOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings


def to_entity(o: AdminOrderSettingsOrmModel) -> AdminOrderSettings:
    return AdminOrderSettings(
        id=o.id,
        public_id=o.public_id,
        order_number_format=o.order_number_format,
        part_number_format=o.part_number_format,
        part_number_auto=o.part_number_auto,
        part_number_editable=o.part_number_editable,
        web_creation_allowed=o.web_creation_allowed,
        pdm_part_number_pattern=o.pdm_part_number_pattern,
        over_delivery_tolerance_percent=o.over_delivery_tolerance_percent,
        under_delivery_tolerance_percent=o.under_delivery_tolerance_percent,
        quote_request_number_format=o.quote_request_number_format,
    )


def to_dict(s: AdminOrderSettings) -> dict[str, Any]:
    return {
        "order_number_format": s.order_number_format,
        "part_number_format": s.part_number_format,
        "part_number_auto": s.part_number_auto,
        "part_number_editable": s.part_number_editable,
        "web_creation_allowed": s.web_creation_allowed,
        "pdm_part_number_pattern": s.pdm_part_number_pattern,
        "over_delivery_tolerance_percent": s.over_delivery_tolerance_percent,
        "under_delivery_tolerance_percent": s.under_delivery_tolerance_percent,
        "quote_request_number_format": s.quote_request_number_format,
    }
