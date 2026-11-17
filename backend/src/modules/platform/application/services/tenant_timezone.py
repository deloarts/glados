"""
The tenant's default timezone, read from the general settings: the zone
calendar hours are local to, every scheduling day is a day of, and dates a
user picks are read in.
"""

from datetime import tzinfo

from src.modules.platform.domain.services.datetime_filters import resolve_actor_timezone
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)


async def tenant_zone(settings_repo: IPlatformSettingsRepository) -> tzinfo:
    """The tenant's default timezone, the one calendar hours are local to
    and every scheduling day is a day of."""
    return resolve_actor_timezone((await settings_repo.get_general()).default_timezone)
