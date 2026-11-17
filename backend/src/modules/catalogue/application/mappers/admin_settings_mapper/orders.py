"""
Maps the order settings entity to its result DTO. The
number examples render for `today`, the tenant's day.
"""

from datetime import date

from src.modules.catalogue.application.dto.admin_settings_dto.orders import AdminOrderSettingsResult
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.platform.domain.services.numbering_format import render_example


class OrderSettingsMapper:
    @staticmethod
    def orders_to_result(e: AdminOrderSettings, *, today: date) -> AdminOrderSettingsResult:
        return AdminOrderSettingsResult(
            id=e.id,
            public_id=e.public_id,
            order_number_format=e.order_number_format,
            example=render_example(e.order_number_format, today=today),
            part_number_format=e.part_number_format,
            part_number_example=render_example(e.part_number_format, today=today),
            part_number_auto=e.part_number_auto,
            part_number_editable=e.part_number_editable,
            web_creation_allowed=e.web_creation_allowed,
            pdm_part_number_pattern=e.pdm_part_number_pattern,
            over_delivery_tolerance_percent=e.over_delivery_tolerance_percent,
            under_delivery_tolerance_percent=e.under_delivery_tolerance_percent,
            quote_request_number_format=e.quote_request_number_format,
            quote_request_number_example=render_example(e.quote_request_number_format, today=today),
        )
