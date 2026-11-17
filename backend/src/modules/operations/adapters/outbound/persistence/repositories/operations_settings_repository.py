"""
SQLAlchemy implementation of the settings section Operations owns: time
tracking.
"""

from src.modules.fulfillment.adapters.outbound.persistence.repositories.fulfillment_settings_repository import (
    SqlAlchemyFulfillmentSettingsRepository,
)
from src.modules.operations.adapters.outbound.persistence.models.admin_settings_model.time_tracking import (
    AdminTimeTrackingSettingsOrmModel,
)
from src.modules.operations.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    time_tracking,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SINGLETON_ID,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    upsert_singleton,
)


class SqlAlchemyOperationsSettingsRepository(
    SqlAlchemyFulfillmentSettingsRepository, IOperationsSettingsRepository
):
    # ── Time tracking ─────────────────────────────────────────────────

    async def get_time_tracking(self) -> AdminTimeTrackingSettings:
        """Nothing seeds the row; the first save inserts it. Until then the
        settings read as time tracking switched off, the safe default,
        instead of failing every capabilities request."""
        orm = await self._db.get(AdminTimeTrackingSettingsOrmModel, SINGLETON_ID)
        if not orm:
            return time_tracking.disabled_defaults()
        return time_tracking.to_entity(orm)

    async def save_time_tracking(self, s: AdminTimeTrackingSettings) -> AdminTimeTrackingSettings:
        orm = await upsert_singleton(
            self._db, AdminTimeTrackingSettingsOrmModel, time_tracking.to_dict(s)
        )
        return time_tracking.to_entity(orm)
