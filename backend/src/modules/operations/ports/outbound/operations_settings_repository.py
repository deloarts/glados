"""
The settings section Operations owns: time tracking.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)


@runtime_checkable
class IOperationsSettingsRepository(IFulfillmentSettingsRepository, Protocol):
    # ── Time tracking ─────────────────────────────────────────────────

    async def get_time_tracking(self) -> AdminTimeTrackingSettings: ...

    async def save_time_tracking(
        self, settings: AdminTimeTrackingSettings
    ) -> AdminTimeTrackingSettings: ...
