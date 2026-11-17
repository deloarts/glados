"""
Unit tests for the Host tab's live statistics: the permission gate and the
mapping from the reader port to the result DTO. The psutil adapter itself is
exercised against the real machine, to catch an API change in psutil rather
than to assert on values that differ per machine.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.adapters.outbound.external.system.psutil_stats_reader import (
    PsutilSystemStatsReader,
)
from src.modules.platform.application.use_cases.admin_settings.get_host_stats import GetHostStats
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.system_stats_port import SystemStats
from tests.factories import make_user

_BOOT = datetime(2026, 8, 1, 6, 0, tzinfo=UTC)
_START = datetime(2026, 8, 12, 9, 30, tzinfo=UTC)


class FakeStatsReader:
    def read(self) -> SystemStats:
        return SystemStats(
            hostname="glados-test",
            platform="Linux 6.1.0-x86_64",
            python_version="3.13.1",
            boot_time=_BOOT,
            process_start_time=_START,
            cpu_count=8,
            cpu_percent=12.5,
            memory_total_bytes=16_000_000_000,
            memory_used_bytes=8_000_000_000,
            memory_percent=50.0,
            disk_total_bytes=500_000_000_000,
            disk_used_bytes=125_000_000_000,
            disk_percent=25.0,
        )


class TestGetHostStats:
    def setup_method(self):
        self.use_case = GetHostStats(FakeStatsReader(), domain="example.com")

    async def test_returns_the_reading_with_the_configured_domain(self):
        result = await self.use_case.execute(
            actor=make_user(permissions=[Permission.READ_SETTINGS])
        )

        assert result.domain == "example.com"
        assert result.hostname == "glados-test"
        assert result.cpu_count == 8
        assert result.cpu_percent == 12.5
        assert result.memory_percent == 50.0
        assert result.disk_percent == 25.0
        assert result.boot_time == _BOOT
        assert result.process_start_time == _START

    async def test_reports_the_running_app_version(self):
        """Taken from src.modules.platform.const, not from the reader, it describes the build,
        not the machine."""
        result = await self.use_case.execute(
            actor=make_user(permissions=[Permission.READ_SETTINGS])
        )
        assert result.app_version

    async def test_unprivileged_cannot_read(self):
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=make_user(permissions=[]))


class TestPsutilSystemStatsReader:
    def test_reads_plausible_values_from_the_real_machine(self):
        """Guards against a psutil API change; the values themselves are
        whatever this machine happens to report."""
        stats = PsutilSystemStatsReader().read()

        assert stats.hostname
        assert stats.platform
        assert stats.cpu_count >= 1
        assert 0.0 <= stats.cpu_percent <= 100.0
        assert stats.memory_total_bytes > 0
        assert 0 <= stats.memory_used_bytes <= stats.memory_total_bytes
        assert stats.disk_total_bytes > 0
        assert 0 <= stats.disk_used_bytes <= stats.disk_total_bytes
        assert stats.boot_time <= stats.process_start_time

    def test_filesystem_id_is_none_for_a_missing_path(self, tmp_path):
        reader = PsutilSystemStatsReader()

        assert isinstance(reader.filesystem_id(str(tmp_path)), int)
        assert reader.filesystem_id(str(tmp_path / "missing")) is None
