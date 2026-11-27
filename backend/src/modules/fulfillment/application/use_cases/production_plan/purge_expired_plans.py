"""
Deletes recorded plans older than the planning settings' retention, with
their rows. It runs with the baseline, under the same advisory lock.
"""

from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_plan_repository import (
    IProductionPlanRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc


class PurgeExpiredPlans:
    def __init__(
        self,
        plan_repo: IProductionPlanRepository,
        settings_repo: IFulfillmentSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._plans = plan_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(self, now: datetime | None = None) -> int:
        """Deletes the plans of every day before today less the retention
        and returns how many it deleted."""
        zone = await tenant_zone(self._settings)
        today = as_utc(now or now_utc()).astimezone(zone).date()
        retention = (await self._settings.get_planning()).plan_retention_days
        deleted = await self._plans.delete_before(today - timedelta(days=retention))
        if deleted:
            await self._uow.commit()
            log.info(f"Purged {deleted} recorded plan(s) older than {retention} days.")
        return deleted
