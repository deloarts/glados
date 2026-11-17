"""
Live machine statistics for the admin Host tab.

Requires read:settings like every other admin settings read. The figures
are not secret in any strong sense, but they describe the deployment rather
than the business data, and there is no reason for an ordinary user's UI to
ask for them.
"""

from src.modules.platform.application.dto.admin_settings_dto.host import HostStatsResult
from src.modules.platform.const import VERSION
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.system_stats_port import ISystemStatsReader


class GetHostStats:
    def __init__(self, reader: ISystemStatsReader, domain: str) -> None:
        self._reader = reader
        self._domain = domain

    async def execute(self, actor: User) -> HostStatsResult:
        SettingsRules.assert_can_read(actor)

        s = self._reader.read()
        return HostStatsResult(
            domain=self._domain,
            hostname=s.hostname,
            platform=s.platform,
            python_version=s.python_version,
            app_version=VERSION,
            boot_time=s.boot_time,
            process_start_time=s.process_start_time,
            cpu_count=s.cpu_count,
            cpu_percent=s.cpu_percent,
            memory_total_bytes=s.memory_total_bytes,
            memory_used_bytes=s.memory_used_bytes,
            memory_percent=s.memory_percent,
            disk_total_bytes=s.disk_total_bytes,
            disk_used_bytes=s.disk_used_bytes,
            disk_percent=s.disk_percent,
        )
