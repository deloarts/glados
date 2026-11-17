"""
Abstract reader for the connectivity status of the services the app depends
on (database, cache, object storage, PDM, the time tracking service, the
stock service). The application layer calls this, never a driver client
directly, so the Host tab's use case stays testable without real
infrastructure underneath it.
"""

from dataclasses import dataclass
from typing import Literal
from typing import Protocol
from typing import runtime_checkable

ServiceStatus = Literal["up", "down", "disabled"]


@dataclass(frozen=True)
class ServiceHealth:
    """A point-in-time reachability check. Nothing here is persisted."""

    name: str  # stable key, e.g. "postgres" | "redis" | "storage" | "pdm"
    label: str  # display label, e.g. "PostgreSQL", "Redis", "SeaweedFS"
    status: ServiceStatus
    latency_ms: float | None  # set only when status == "up"
    detail: str | None  # error message, set only when status == "down"


@runtime_checkable
class IServiceHealthChecker(Protocol):
    async def check(self) -> list[ServiceHealth]: ...
