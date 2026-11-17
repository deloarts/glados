"""
A tick that a device is in one of the plans outside Glados (see
device_plan.py), such as its CAD assembly or the EPLAN plan, so nothing is
forgotten between disciplines. It records who ticked it and when.
Renaming the device takes its ticks away, because each of those plans
carries the name and has to follow.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductDeviceCheck(Entity):
    device_id: int
    plan: DevicePlan
    checked_by_id: int
    checked_at: datetime
    # Denormalized (read-only, populated by repository mapper).
    checked_by_name: str = ""
