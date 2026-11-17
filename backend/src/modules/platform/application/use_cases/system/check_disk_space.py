"""
Measures disk usage on "/" and (when configured
and present) storage.backup_path, and alerts via
IMailService.send_disc_space_warning when the worse of the two is at or
above storage.disk_warning_percent. Runs every 15 minutes as an interval
job started by BackupScheduler (system_schedule.py).

- `disk_warning_percent == 0` disables the check entirely (the shipped
  default is 90).
- Filesystems are deduped by the stats reader's filesystem_id: a configured
  backup_path that lives on the same filesystem as "/" (the common case)
  must not be measured, and therefore alerted on, twice. A path whose id
  cannot be read (missing or unreadable) is skipped.
- Only the worse (higher-percent-full) of the measured filesystems is
  reported when more than one is at/above threshold: one mail, not one
  per filesystem.
- Cooldown: claims `alert:disk_space` for 24h via IReplayGuard.consume_once
  *before* sending, same "claim first" reasoning as NotifyScheduleError.
- Entirely non-fatal: a bad backup_path, a psutil failure, a
  Redis hiccup, or an SMTP failure all end up logged, never raised, since this
  runs unattended on a scheduler tick with nobody to catch an exception.
"""

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.system_stats_port import ISystemStatsReader

_ALERT_KEY = "alert:disk_space"
_COOLDOWN_TTL_SECONDS = 24 * 60 * 60  # 24h
_BYTES_PER_GB = 1024**3


class CheckDiskSpace:
    def __init__(
        self,
        stats_reader: ISystemStatsReader,
        admin_settings_repo: IPlatformSettingsRepository,
        mail_service: IMailService,
        replay_guard: IReplayGuard,
    ) -> None:
        self._stats_reader = stats_reader
        self._admin_settings = admin_settings_repo
        self._mail = mail_service
        self._replay_guard = replay_guard

    async def execute(self) -> None:
        try:
            await self._check()
        except Exception:
            log.error("CheckDiskSpace: failed to check/alert on disk usage.", exc_info=True)

    async def _check(self) -> None:
        storage = await self._admin_settings.get_storage()
        threshold = storage.disk_warning_percent
        if threshold <= 0:
            return  # disabled

        paths = ["/"]
        if storage.backup_path:
            paths.append(storage.backup_path)

        seen_devices: set[int] = set()
        worst_percent = -1.0
        worst: tuple[int, int] | None = None  # (used, total) bytes, of the worst filesystem
        for path in paths:
            # None means the path is missing or unreadable, so it is skipped.
            device = self._stats_reader.filesystem_id(path)
            if device is None or device in seen_devices:
                continue
            seen_devices.add(device)

            used, total = self._stats_reader.disk_usage(path)
            if total <= 0:
                continue
            percent = used / total * 100
            if percent > worst_percent:
                worst_percent = percent
                worst = (used, total)

        if worst is None or worst_percent < threshold:
            return

        if not await self._replay_guard.consume_once(_ALERT_KEY, _COOLDOWN_TTL_SECONDS):
            log.debug("CheckDiskSpace: already alerted within the last 24h, skipping.")
            return

        used, total = worst
        await self._mail.send_disc_space_warning(
            round(used / _BYTES_PER_GB, 1), round(total / _BYTES_PER_GB, 1)
        )
