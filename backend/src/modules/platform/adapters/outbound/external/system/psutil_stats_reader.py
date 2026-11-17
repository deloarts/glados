"""
Reads live machine statistics via psutil. Infrastructure detail, the
application layer depends on ISystemStatsReader, never on this module.

Inside a container these figures describe the container's view: the disk is the
filesystem the app runs from, and memory/CPU reflect whatever the runtime
exposes. On a cgroup-limited container that is the host's totals rather than
the limit, which is worth knowing when reading the numbers, but it is what an
operator looking at "is this box busy" actually wants.
"""

import os
import platform
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

import psutil

from src.modules.platform.ports.outbound.system_stats_port import SystemStats

# Path whose filesystem is reported. "/" is the container root, which is where
# the app and its local storage live unless a volume is mounted elsewhere.
_DISK_PATH = "/"


class PsutilSystemStatsReader:
    def read(self) -> SystemStats:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(_DISK_PATH)

        # interval=None returns the percentage since the previous call rather
        # than blocking to sample. The first call after import therefore reports
        # 0.0; every later one, including the UI's 5-second poll, is a real
        # reading. Blocking for a sample would hold a worker thread on an
        # endpoint that gets polled continuously.
        cpu_percent = psutil.cpu_percent(interval=None)

        return SystemStats(
            hostname=platform.node(),
            platform=f"{platform.system()} {platform.release()}-{platform.machine()}",
            python_version=sys.version.split()[0],
            boot_time=datetime.fromtimestamp(psutil.boot_time(), tz=UTC),
            process_start_time=datetime.fromtimestamp(
                psutil.Process(os.getpid()).create_time(), tz=UTC
            ),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            cpu_percent=cpu_percent,
            memory_total_bytes=memory.total,
            memory_used_bytes=memory.total - memory.available,
            memory_percent=memory.percent,
            disk_total_bytes=disk.total,
            disk_used_bytes=disk.used,
            disk_percent=disk.percent,
        )

    def disk_usage(self, path: str) -> tuple[int, int]:
        usage = psutil.disk_usage(path)
        return usage.used, usage.total

    def filesystem_id(self, path: str) -> int | None:
        try:
            return Path(path).stat().st_dev
        except OSError:
            return None
