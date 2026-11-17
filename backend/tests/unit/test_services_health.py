"""
Unit tests for the Host tab's connected-services panel: the permission gate
and DTO mapping in GetServicesHealth, and the up/down/disabled branching in
the ServiceHealthChecker adapter itself, including the PDM, time tracking
service and stock service cards.
"""

import asyncio

import pytest

from src.bootstrap.adapters.outbound.external.system import service_health_checker
from src.bootstrap.adapters.outbound.external.system.service_health_checker import (
    ServiceHealthChecker,
)
from src.modules.platform.application.use_cases.admin_settings.get_services_health import (
    GetServicesHealth,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.service_health_port import ServiceHealth
from tests.factories import make_user


def _storage_settings(*, provider: str = "seaweedfs", enabled: bool = True) -> AdminStorageSettings:
    return AdminStorageSettings(
        id=1,
        provider=provider,
        enabled=enabled,
        endpoint_url="http://seaweedfs:8333",
        public_endpoint_url=None,
        bucket_name="glados",
        access_key="key",
        secret_key="secret",
        region=None,
        use_ssl=False,
        backup_enabled=False,
        backup_path=None,
        backup_cron=None,
        backup_retention_count=7,
    )


class FakeChecker:
    def __init__(self, services: list[ServiceHealth]) -> None:
        self._services = services

    async def check(self) -> list[ServiceHealth]:
        return self._services


class TestGetServicesHealth:
    async def test_maps_each_service_through(self):
        services = [
            ServiceHealth("postgres", "PostgreSQL", "up", 1.2, None),
            ServiceHealth("redis", "Redis", "down", None, "connection refused"),
            ServiceHealth("storage", "SeaweedFS", "disabled", None, None),
        ]
        use_case = GetServicesHealth(FakeChecker(services))

        result = await use_case.execute(actor=make_user(permissions=[Permission.READ_SETTINGS]))

        assert [s.name for s in result.services] == ["postgres", "redis", "storage"]
        assert result.services[0].status == "up"
        assert result.services[0].latency_ms == 1.2
        assert result.services[1].status == "down"
        assert result.services[1].detail == "connection refused"
        assert result.services[2].status == "disabled"

    async def test_unprivileged_cannot_read(self):
        use_case = GetServicesHealth(FakeChecker([]))
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=make_user(permissions=[]))


class FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def execute(self, _stmt):
        if self._fail:
            raise RuntimeError("connection refused")


class FakeRedisClient:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise RuntimeError("connection refused")
        return True


class FakeStorageAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def test_connection(self) -> None:
        if self._fail:
            raise RuntimeError("bucket not found")


class TestServiceHealthChecker:
    async def test_postgres_up(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=None,
            storage_settings=_storage_settings(enabled=False),
        )
        result = next(s for s in await checker.check() if s.name == "postgres")
        assert result.status == "up"
        assert result.latency_ms is not None

    async def test_postgres_down(self):
        checker = ServiceHealthChecker(
            db=FakeSession(fail=True),
            redis_client=FakeRedisClient(),
            storage=None,
            storage_settings=_storage_settings(enabled=False),
        )
        result = next(s for s in await checker.check() if s.name == "postgres")
        assert result.status == "down"
        assert result.detail == "connection refused"

    async def test_redis_down(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(fail=True),
            storage=None,
            storage_settings=_storage_settings(enabled=False),
        )
        result = next(s for s in await checker.check() if s.name == "redis")
        assert result.status == "down"
        assert result.detail == "connection refused"

    async def test_storage_disabled_reports_disabled_not_down(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=None,
            storage_settings=_storage_settings(provider="seaweedfs", enabled=False),
        )
        result = next(s for s in await checker.check() if s.name == "storage")
        assert result.status == "disabled"
        assert result.label == "SeaweedFS"

    async def test_storage_up_uses_provider_label(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=FakeStorageAdapter(),
            storage_settings=_storage_settings(provider="s3", enabled=True),
        )
        result = next(s for s in await checker.check() if s.name == "storage")
        assert result.status == "up"
        assert result.label == "Amazon S3"

    async def test_storage_down_surfaces_the_error(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=FakeStorageAdapter(fail=True),
            storage_settings=_storage_settings(provider="azure", enabled=True),
        )
        result = next(s for s in await checker.check() if s.name == "storage")
        assert result.status == "down"
        assert result.detail == "bucket not found"

    async def test_pdm_and_time_tracking_disabled_without_a_client(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=None,
            storage_settings=_storage_settings(enabled=False),
        )
        results = {s.name: s for s in await checker.check()}
        assert results["pdm"].status == "disabled"
        assert results["pdm"].label == "SolidWorks PDM"
        assert results["time_tracking"].status == "disabled"
        assert results["time_tracking"].label == "Time tracking service"

    async def test_stock_service_disabled_without_a_client_and_up_with_one(self):
        def checker(stock: object | None) -> ServiceHealthChecker:
            return ServiceHealthChecker(
                db=FakeSession(),
                redis_client=FakeRedisClient(),
                storage=None,
                storage_settings=_storage_settings(enabled=False),
                stock=stock,  # type: ignore[arg-type]
            )

        disabled = next(s for s in await checker(None).check() if s.name == "stock")
        up = next(s for s in await checker(FakeHealthProbe()).check() if s.name == "stock")

        assert disabled.status == "disabled"
        assert disabled.label == "Stock service"
        assert up.status == "up"
        assert up.latency_ms is not None

    async def test_pdm_up_and_time_tracking_down(self):
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=None,
            storage_settings=_storage_settings(enabled=False),
            pdm=FakePdmGateway(),  # type: ignore[arg-type]
            time_tracking=FakeHealthProbe(fail=True),  # type: ignore[arg-type]
        )
        results = {s.name: s for s in await checker.check()}
        assert results["pdm"].status == "up"
        assert results["pdm"].latency_ms is not None
        assert results["time_tracking"].status == "down"
        assert results["time_tracking"].detail == "connection refused"

    async def test_remote_probe_times_out(self, monkeypatch):
        monkeypatch.setattr(service_health_checker, "_PROBE_TIMEOUT_SECONDS", 0.01)
        checker = ServiceHealthChecker(
            db=FakeSession(),
            redis_client=FakeRedisClient(),
            storage=None,
            storage_settings=_storage_settings(enabled=False),
            pdm=FakePdmGateway(hang=True),  # type: ignore[arg-type]
        )
        result = next(s for s in await checker.check() if s.name == "pdm")
        assert result.status == "down"
        assert result.detail == "Timed out"


class FakePdmGateway:
    def __init__(self, *, hang: bool = False) -> None:
        self._hang = hang

    async def version(self) -> None:
        if self._hang:
            await asyncio.sleep(1)


class FakeHealthProbe:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def health(self) -> None:
        if self._fail:
            raise RuntimeError("connection refused")
