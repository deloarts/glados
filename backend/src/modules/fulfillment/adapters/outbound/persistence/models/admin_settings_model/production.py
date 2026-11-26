"""
ORM model for the admin_production_settings singleton table. Its
default_inspection_method_id is the one foreign key from an admin
settings table into the catalogue.
"""

import json
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base

_WORKDAY = [{"start_minute": 480, "minutes": 480}]
DEFAULT_WEEKLY_HOURS_JSON = json.dumps(
    {str(day): _WORKDAY if day < 5 else [] for day in range(7)}, separators=(",", ":")
)


class AdminProductionSettingsOrmModel(Base):
    __tablename__ = "admin_production_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    production_order_number_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="PON-{yy}-{seq:05d}"
    )
    # weekday (str "0"=Monday..str "6"=Sunday) -> working intervals
    # (repositories/_calendar_hours.py), Monday to Friday 08:00 for 8 hours.
    default_weekly_hours: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: json.loads(DEFAULT_WEEKLY_HOURS_JSON),
        server_default=DEFAULT_WEEKLY_HOURS_JSON,
    )
    default_external_lead_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    response_time_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    internal_handoff_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    external_safety_margin_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default="2"
    )
    require_qa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    frozen_window_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    require_source_item_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    assign_approved_material_to_item: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    overwrite_item_material_on_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    external_first_step_needs_no_material: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    default_inspection_method_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "inspection_method_table.id", name="fk_admin_production_settings_inspection_method_id"
        ),
        nullable=True,
        index=True,
    )
