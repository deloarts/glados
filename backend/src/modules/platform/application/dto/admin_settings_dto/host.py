"""
Commands and results for the host settings, plus the live host stats and
service health readouts.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class AdminHostSettingsResult(ResultBase):
    """No stored fields left, the contact address and legal URLs moved to the
    general domain. `domain` comes from config, not the database."""

    domain: str


class HostStatsResult(BaseModel):
    """A point-in-time reading of the machine the backend runs on.

    Read live on every request, never stored. Disk figures describe the
    container filesystem the app runs from, not the configured file-storage
    backend, that is a separate concern with its own admin tab.
    """

    domain: str
    hostname: str
    platform: str  # e.g. "Linux 6.1.0-x86_64"
    python_version: str
    app_version: str
    boot_time: datetime  # of the host, not the app process
    process_start_time: datetime

    cpu_count: int
    cpu_percent: float  # 0-100, across all cores

    memory_total_bytes: int
    memory_used_bytes: int
    memory_percent: float

    disk_total_bytes: int
    disk_used_bytes: int
    disk_percent: float


class ServiceHealthResult(BaseModel):
    """A point-in-time reachability check for one connected service."""

    name: str  # stable key, e.g. "postgres" | "redis" | "storage"
    label: str  # display label, e.g. "PostgreSQL", "Redis", "SeaweedFS"
    status: str  # "up" | "down" | "disabled"
    latency_ms: float | None
    detail: str | None


class ServicesHealthResult(BaseModel):
    """Connectivity status of every service the Host tab's panel shows.

    Read live on every request, never stored, same reasoning as
    HostStatsResult.
    """

    services: list[ServiceHealthResult]
