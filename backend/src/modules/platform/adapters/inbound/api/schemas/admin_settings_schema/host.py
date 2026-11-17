"""
HTTP request and response schemas for the host settings, plus the live host
stats and service health readouts.
"""

from datetime import datetime

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.ports.outbound.service_health_port import ServiceStatus


class AdminHostSettingsResponse(EntityResponse):
    domain: str


class HostStatsResponse(ResponseModel):
    domain: str
    hostname: str
    platform: str
    python_version: str
    app_version: str
    boot_time: datetime
    process_start_time: datetime

    cpu_count: int
    cpu_percent: float

    memory_total_bytes: int
    memory_used_bytes: int
    memory_percent: float

    disk_total_bytes: int
    disk_used_bytes: int
    disk_percent: float


class ServiceHealthResponse(ResponseModel):
    name: str
    label: str
    status: ServiceStatus
    latency_ms: float | None
    detail: str | None


class ServicesHealthResponse(ResponseModel):
    services: list[ServiceHealthResponse]
