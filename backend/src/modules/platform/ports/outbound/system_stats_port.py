"""
Abstract reader for live machine statistics. The application layer calls this,
never psutil directly, so the Host tab's use case stays testable without a real
machine underneath it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class SystemStats:
    """A point-in-time reading. Nothing here is persisted."""

    hostname: str
    platform: str  # e.g. "Linux 6.1.0-x86_64"
    python_version: str
    boot_time: datetime  # of the host, not the app process
    process_start_time: datetime

    cpu_count: int
    cpu_percent: float  # 0-100, across all cores

    memory_total_bytes: int
    memory_used_bytes: int
    memory_percent: float

    # The filesystem the app runs from, not the configured file-storage
    # backend, which the Storage tab covers separately.
    disk_total_bytes: int
    disk_used_bytes: int
    disk_percent: float


@runtime_checkable
class ISystemStatsReader(Protocol):
    def read(self) -> SystemStats: ...

    def disk_usage(self, path: str) -> tuple[int, int]:
        """(used_bytes, total_bytes) for the filesystem containing `path`.
        Used by CheckDiskSpace to measure "/" and an optional configured
        backup_path independently of the Host tab's own single-path
        `read()` snapshot."""
        ...

    def filesystem_id(self, path: str) -> int | None:
        """The device id of the filesystem containing `path`, or None when
        the path does not exist or cannot be read. CheckDiskSpace compares
        these ids so two paths on one filesystem are measured once."""
        ...
