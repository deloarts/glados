"""
Unit tests for CheckDiskSpace: threshold gating, filesystem dedupe by
device id, cooldown, and non-fatal behaviour throughout. A fake stats reader
supplies both the usage and the device id per path, so the test never
depends on the real filesystem's actual usage or a real backup_path.
"""

from types import SimpleNamespace

from src.modules.platform.application.use_cases.system.check_disk_space import CheckDiskSpace


def make_storage(backup_path: str | None = None, disk_warning_percent: int = 90):
    return SimpleNamespace(backup_path=backup_path, disk_warning_percent=disk_warning_percent)


class FakeAdminSettingsRepo:
    def __init__(self, storage) -> None:
        self._storage = storage

    async def get_storage(self):
        return self._storage


class FakeStatsReader:
    """Paths missing from `devices` read as missing or unreadable."""

    def __init__(
        self, usage: dict[str, tuple[int, int]], devices: dict[str, int] | None = None
    ) -> None:
        self._usage = usage
        self._devices = devices or {}

    def disk_usage(self, path: str) -> tuple[int, int]:
        return self._usage[path]

    def filesystem_id(self, path: str) -> int | None:
        return self._devices.get(path)

    def read(self):  # pragma: no cover - not used by CheckDiskSpace
        raise NotImplementedError


class FakeMailService:
    def __init__(self) -> None:
        self.sent: list[tuple[float, float]] = []

    async def send_disc_space_warning(self, used_gb: float, total_gb: float) -> None:
        self.sent.append((used_gb, total_gb))


class FakeReplayGuard:
    def __init__(self, *, claims: bool = True) -> None:
        self.claims = claims
        self.calls: list[tuple[str, int]] = []

    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        self.calls.append((key, ttl_seconds))
        return self.claims


class TestBelowThreshold:
    async def test_no_send_when_usage_is_below_the_threshold(self):
        storage = make_storage(disk_warning_percent=90)
        stats = FakeStatsReader({"/": (50 * 1024**3, 100 * 1024**3)}, devices={"/": 1})  # 50%
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        assert mail.sent == []


class TestAtOrAboveThreshold:
    async def test_sends_when_usage_is_at_or_above_the_threshold(self):
        storage = make_storage(disk_warning_percent=90)
        stats = FakeStatsReader({"/": (95 * 1024**3, 100 * 1024**3)}, devices={"/": 1})  # 95%
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        assert mail.sent == [(95.0, 100.0)]

    async def test_reports_the_worse_of_two_filesystems(self):
        storage = make_storage(backup_path="/mnt/backup", disk_warning_percent=90)
        stats = FakeStatsReader(
            {
                "/": (91 * 1024**3, 100 * 1024**3),  # 91%
                "/mnt/backup": (99 * 1024**3, 100 * 1024**3),  # 99%, worse
            },
            devices={"/": 1, "/mnt/backup": 2},
        )
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        assert mail.sent == [(99.0, 100.0)]


class TestThresholdZeroDisables:
    async def test_zero_percent_threshold_disables_the_check_entirely(self):
        storage = make_storage(disk_warning_percent=0)
        stats = FakeStatsReader({"/": (99 * 1024**3, 100 * 1024**3)}, devices={"/": 1})
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        assert mail.sent == []


class TestFilesystemDedupe:
    async def test_a_backup_path_on_the_same_device_as_root_is_measured_once(self):
        """Both paths resolve to device id 1 (the common case: backup_path
        lives on the root filesystem): only "/" (the first one checked)
        may be measured, never both."""
        storage = make_storage(backup_path="/var/backups", disk_warning_percent=90)
        # Only "/" is in the usage map. If the dedupe failed and the
        # backup_path were measured too, this would KeyError.
        stats = FakeStatsReader(
            {"/": (95 * 1024**3, 100 * 1024**3)}, devices={"/": 1, "/var/backups": 1}
        )
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        assert mail.sent == [(95.0, 100.0)]


class TestMissingBackupPath:
    async def test_a_backup_path_that_does_not_exist_is_skipped(self):
        storage = make_storage(backup_path="/mnt/gone", disk_warning_percent=90)
        stats = FakeStatsReader({"/": (95 * 1024**3, 100 * 1024**3)}, devices={"/": 1})
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        # Would KeyError on "/mnt/gone" if it were measured despite not existing.
        assert mail.sent == [(95.0, 100.0)]

    async def test_no_backup_path_configured_only_measures_root(self):
        storage = make_storage(backup_path=None, disk_warning_percent=90)
        stats = FakeStatsReader({"/": (10 * 1024**3, 100 * 1024**3)}, devices={"/": 1})
        mail = FakeMailService()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()

        assert mail.sent == []


class TestCooldown:
    async def test_a_second_check_within_the_cooldown_does_not_resend(self):
        storage = make_storage(disk_warning_percent=90)
        stats = FakeStatsReader({"/": (95 * 1024**3, 100 * 1024**3)}, devices={"/": 1})
        mail = FakeMailService()
        guard = FakeReplayGuard(claims=False)

        await CheckDiskSpace(stats, FakeAdminSettingsRepo(storage), mail, guard).execute()

        assert mail.sent == []
        assert guard.calls == [("alert:disk_space", 24 * 60 * 60)]

    async def test_below_threshold_never_even_consults_the_guard(self):
        storage = make_storage(disk_warning_percent=90)
        stats = FakeStatsReader({"/": (10 * 1024**3, 100 * 1024**3)}, devices={"/": 1})
        guard = FakeReplayGuard()

        await CheckDiskSpace(
            stats, FakeAdminSettingsRepo(storage), FakeMailService(), guard
        ).execute()

        assert guard.calls == []


class TestNonFatal:
    async def test_a_stat_failure_is_swallowed_not_raised(self):
        # The fake reader knows no device ids, so "/" reads as unreadable.
        storage = make_storage(disk_warning_percent=90)
        mail = FakeMailService()

        await CheckDiskSpace(
            FakeStatsReader({}), FakeAdminSettingsRepo(storage), mail, FakeReplayGuard()
        ).execute()  # must not raise

        assert mail.sent == []

    async def test_a_totally_unexpected_exception_is_swallowed(self):
        class ExplodingRepo:
            async def get_storage(self):
                raise RuntimeError("db exploded")

        mail = FakeMailService()

        await CheckDiskSpace(
            FakeStatsReader({}), ExplodingRepo(), mail, FakeReplayGuard()
        ).execute()  # must not raise

        assert mail.sent == []
