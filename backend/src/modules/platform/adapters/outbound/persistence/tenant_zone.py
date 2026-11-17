"""
The tenant's timezone as the persistence layer reads it, straight from the
general settings row.

The whole app reads calendar days in one timezone, the tenant's default
timezone from the general settings. A repository that turns a calendar-date
filter into UTC bounds (date_range.py) resolves the zone once per query
method with `date_filter_zone` and hands it down to its filter builders, so
"created on 2026-11-02" means that day in Vienna, not in UTC.
"""

from datetime import UTC
from datetime import date
from datetime import tzinfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.platform_settings_repository import (
    SINGLETON_ID,
)
from src.modules.platform.domain.services.datetime_filters import resolve_actor_timezone


async def read_tenant_zone(db: AsyncSession) -> tzinfo:
    """The tenant's default timezone, UTC when the general settings name
    none or an unknown one."""
    name = await db.scalar(
        select(AdminGeneralSettingsOrmModel.default_timezone).where(
            AdminGeneralSettingsOrmModel.id == SINGLETON_ID
        )
    )
    return resolve_actor_timezone(name or "UTC")


async def date_filter_zone(db: AsyncSession, *days: date | None) -> tzinfo:
    """The zone the calendar days of a list filter are read in, the tenant's.

    It is read only when one of `days` is set. With none set no day bound
    is built from the zone, so UTC stands in and no query runs."""
    if all(day is None for day in days):
        return UTC
    return await read_tenant_zone(db)
