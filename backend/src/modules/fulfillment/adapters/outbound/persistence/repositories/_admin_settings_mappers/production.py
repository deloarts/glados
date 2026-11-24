"""
Row mapping for the admin_production_settings singleton. Converts the ORM row
to the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.fulfillment.adapters.outbound.persistence.models.admin_settings_model.production import (
    AdminProductionSettingsOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._calendar_hours import (
    weekly_from_json,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._calendar_hours import (
    weekly_to_json,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)


def to_entity(o: AdminProductionSettingsOrmModel) -> AdminProductionSettings:
    return AdminProductionSettings(
        id=o.id,
        public_id=o.public_id,
        production_order_number_format=o.production_order_number_format,
        default_weekly_hours=weekly_from_json(o.default_weekly_hours),
        default_external_lead_days=o.default_external_lead_days,
        response_time_days=o.response_time_days,
        external_safety_margin_days=o.external_safety_margin_days,
        require_qa=o.require_qa,
        frozen_window_hours=o.frozen_window_hours,
        require_source_item_approval=o.require_source_item_approval,
        assign_approved_material_to_item=o.assign_approved_material_to_item,
        overwrite_item_material_on_approval=o.overwrite_item_material_on_approval,
        external_first_step_needs_no_material=o.external_first_step_needs_no_material,
        default_inspection_method_id=o.default_inspection_method_id,
    )


def to_dict(s: AdminProductionSettings) -> dict[str, Any]:
    return {
        "production_order_number_format": s.production_order_number_format,
        "default_weekly_hours": weekly_to_json(s.default_weekly_hours),
        "default_external_lead_days": s.default_external_lead_days,
        "response_time_days": s.response_time_days,
        "external_safety_margin_days": s.external_safety_margin_days,
        "require_qa": s.require_qa,
        "frozen_window_hours": s.frozen_window_hours,
        "require_source_item_approval": s.require_source_item_approval,
        "assign_approved_material_to_item": s.assign_approved_material_to_item,
        "overwrite_item_material_on_approval": s.overwrite_item_material_on_approval,
        "external_first_step_needs_no_material": s.external_first_step_needs_no_material,
        "default_inspection_method_id": s.default_inspection_method_id,
    }
