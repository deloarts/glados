"""
Pings the external services the app depends on, for the admin Host tab's
service-status panel. Each check is a cheap, side-effect-free round trip,
SELECT 1, PING, the storage backend's own test_connection(), the PDM Web
API's unauthenticated version endpoint or the /health of the time tracking
and the stock service, never a write and never a login, so it is safe to
run on every poll.

The checks run concurrently and each remote probe is capped at a few
seconds, so one unreachable server cannot hold the whole panel up for its
full connection timeout while the tab keeps polling.
"""

import asyncio
import time
from collections.abc import Awaitable

import redis.asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.stock_service_port import IStockService
from src.modules.operations.ports.outbound.time_tracking_provider_port import ITimeTrackingProvider
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.ports.outbound.service_health_port import ServiceHealth
from src.modules.platform.ports.outbound.storage_port import IStoragePort

_PROBE_TIMEOUT_SECONDS = 4.0

_STORAGE_LABELS = {
    "local": "Local Disk",
    "seaweedfs": "SeaweedFS",
    "s3": "Amazon S3",
    "azure": "Azure Blob",
}


class ServiceHealthChecker:
    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.asyncio.Redis,
        storage: IStoragePort | None,
        storage_settings: AdminStorageSettings,
        pdm: IPdmGateway | None = None,
        time_tracking: ITimeTrackingProvider | None = None,
        stock: IStockService | None = None,
    ) -> None:
        """A None gateway means the integration is switched off or not fully
        configured, which the panel shows as disabled rather than down."""
        self._db = db
        self._redis = redis_client
        self._storage = storage
        self._storage_settings = storage_settings
        self._pdm = pdm
        self._time_tracking = time_tracking
        self._stock = stock

    async def check(self) -> list[ServiceHealth]:
        return list(
            await asyncio.gather(
                self._check_postgres(),
                self._check_redis(),
                self._check_storage(),
                self._check_pdm(),
                self._check_time_tracking(),
                self._check_stock(),
            )
        )

    async def _check_postgres(self) -> ServiceHealth:
        start = time.monotonic()
        try:
            await self._db.execute(text("SELECT 1"))
            return ServiceHealth("postgres", "PostgreSQL", "up", _elapsed_ms(start), None)
        except Exception as exc:
            return ServiceHealth("postgres", "PostgreSQL", "down", None, str(exc))

    async def _check_redis(self) -> ServiceHealth:
        start = time.monotonic()
        try:
            await self._redis.ping()
            return ServiceHealth("redis", "Redis", "up", _elapsed_ms(start), None)
        except Exception as exc:
            return ServiceHealth("redis", "Redis", "down", None, str(exc))

    async def _check_storage(self) -> ServiceHealth:
        provider = self._storage_settings.provider
        label = _STORAGE_LABELS.get(provider, provider)
        if not self._storage_settings.enabled or self._storage is None:
            return ServiceHealth("storage", label, "disabled", None, None)

        start = time.monotonic()
        try:
            await self._storage.test_connection()
            return ServiceHealth("storage", label, "up", _elapsed_ms(start), None)
        except Exception as exc:
            return ServiceHealth("storage", label, "down", None, str(exc))

    async def _check_pdm(self) -> ServiceHealth:
        if self._pdm is None:
            return ServiceHealth("pdm", "SolidWorks PDM", "disabled", None, None)
        return await _probe("pdm", "SolidWorks PDM", self._pdm.version())

    async def _check_time_tracking(self) -> ServiceHealth:
        label = "Time tracking service"
        if self._time_tracking is None:
            return ServiceHealth("time_tracking", label, "disabled", None, None)
        return await _probe("time_tracking", label, self._time_tracking.health())

    async def _check_stock(self) -> ServiceHealth:
        label = "Stock service"
        if self._stock is None:
            return ServiceHealth("stock", label, "disabled", None, None)
        return await _probe("stock", label, self._stock.health())


async def _probe(name: str, label: str, call: Awaitable[object]) -> ServiceHealth:
    start = time.monotonic()
    try:
        await asyncio.wait_for(call, timeout=_PROBE_TIMEOUT_SECONDS)
        return ServiceHealth(name, label, "up", _elapsed_ms(start), None)
    except TimeoutError:
        return ServiceHealth(name, label, "down", None, "Timed out")
    except Exception as exc:
        return ServiceHealth(name, label, "down", None, str(exc) or type(exc).__name__)


def _elapsed_ms(start: float) -> float:
    return round((time.monotonic() - start) * 1000, 1)
