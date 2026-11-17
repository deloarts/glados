"""
Maps the production settings entity to its result DTO. The
number examples render for `today`, the tenant's day.
"""

from datetime import date

from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    AdminProductionSettingsResult,
)
from src.modules.fulfillment.application.mappers.machine_calendar_mapper import weekly_hours_to_dto
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.services.numbering_format import render_example


class ProductionSettingsMapper:
    @staticmethod
    def production_to_result(
        e: AdminProductionSettings, *, today: date
    ) -> AdminProductionSettingsResult:
        return AdminProductionSettingsResult(
            id=e.id,
            public_id=e.public_id,
            production_order_number_format=e.production_order_number_format,
            default_weekly_hours=weekly_hours_to_dto(e.default_weekly_hours),
            default_external_lead_days=e.default_external_lead_days,
            response_time_days=e.response_time_days,
            require_qa=e.require_qa,
            frozen_window_hours=e.frozen_window_hours,
            default_inspection_method_id=e.default_inspection_method_id,
            require_source_item_approval=e.require_source_item_approval,
            assign_approved_material_to_item=e.assign_approved_material_to_item,
            overwrite_item_material_on_approval=e.overwrite_item_material_on_approval,
            example=render_example(e.production_order_number_format, today=today),
        )
