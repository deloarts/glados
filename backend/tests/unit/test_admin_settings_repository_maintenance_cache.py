"""
Unit tests for the process-local TTL cache get_maintenance() layers on top
of the admin_maintenance_settings singleton row (see
admin_settings_repository.py's module docstring for the rationale). Real
in-memory SQLite sessions, not a fake repository, because the whole point
of the cache is that a second database round trip is provably absent (or
present, once the TTL or an invalidating save force one), and a fake could not
stand in for that proof. Each test points a repository at its own fresh,
otherwise-empty engine so a returned value can only have come from the
cache, never from that engine's own row.

tests/conftest.py's autouse `_clear_maintenance_cache` fixture already
clears this module-global cache before every test in the suite; these
tests are what that fixture exists to protect the rest of the suite from.
"""

from collections.abc import AsyncIterator
from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.maintenance import (
    AdminMaintenanceSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.repositories import (
    platform_settings_repository as admin_settings_repository,
)
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings


class _FakeClock:
    """Stands in for time.monotonic() so the cache's TTL can be crossed
    deterministically, without sleeping in a test."""

    def __init__(self, start: float = 1_000.0) -> None:
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


_opened: list[tuple[AsyncSession, AsyncEngine]] = []


async def _new_session(seed: AdminMaintenanceSettingsOrmModel | None = None) -> AsyncSession:
    """A session bound to its own fresh in-memory SQLite engine, optionally
    seeded with one admin_maintenance_settings row. A dedicated engine per
    call, not a shared one, is the point: a repository bound to a second,
    unseeded database can only return a correct row from the cache."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[AdminMaintenanceSettingsOrmModel.__table__]
        )
    session = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    _opened.append((session, engine))
    if seed is not None:
        session.add(seed)
        await session.commit()
    return session


@pytest.fixture(autouse=True)
def _reset_cache() -> Iterator[None]:
    """Belt-and-braces on top of tests/conftest.py's own autouse fixture:
    this module is exactly what that fixture protects, so it must not
    depend on fixture load order to start and end each test clean."""
    admin_settings_repository.clear_maintenance_cache()
    yield
    admin_settings_repository.clear_maintenance_cache()


@pytest.fixture(autouse=True)
async def _close_sessions() -> AsyncIterator[None]:
    """Closes every session and engine _new_session opened during the test."""
    yield
    while _opened:
        session, engine = _opened.pop()
        await session.close()
        await engine.dispose()


class TestCacheHit:
    async def test_hit_within_ttl_does_not_query_again(self):
        primed = await _new_session(
            AdminMaintenanceSettingsOrmModel(id=1, enabled=False, message="from A", allowed_ips=[])
        )
        await SqlAlchemyAdminSettingsRepository(primed).get_maintenance()

        empty = await _new_session()  # no row at all; a real query here would raise
        result = await SqlAlchemyAdminSettingsRepository(empty).get_maintenance()

        assert result.enabled is False
        assert result.message == "from A"


class TestCacheExpiry:
    async def test_expiry_after_ttl_queries_again(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = _FakeClock()
        monkeypatch.setattr(admin_settings_repository, "time", clock)

        primed = await _new_session(
            AdminMaintenanceSettingsOrmModel(id=1, enabled=False, message="stale", allowed_ips=[])
        )
        await SqlAlchemyAdminSettingsRepository(primed).get_maintenance()

        clock.advance(admin_settings_repository.MAINTENANCE_CACHE_TTL_S + 0.01)

        fresh = await _new_session(
            AdminMaintenanceSettingsOrmModel(id=1, enabled=True, message="fresh", allowed_ips=[])
        )
        result = await SqlAlchemyAdminSettingsRepository(fresh).get_maintenance()

        assert result.enabled is True
        assert result.message == "fresh"

    async def test_still_cached_just_before_ttl_expires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = _FakeClock()
        monkeypatch.setattr(admin_settings_repository, "time", clock)

        primed = await _new_session(
            AdminMaintenanceSettingsOrmModel(id=1, enabled=False, message="from A", allowed_ips=[])
        )
        await SqlAlchemyAdminSettingsRepository(primed).get_maintenance()

        clock.advance(admin_settings_repository.MAINTENANCE_CACHE_TTL_S - 0.01)

        empty = await _new_session()
        result = await SqlAlchemyAdminSettingsRepository(empty).get_maintenance()

        assert result.message == "from A"


class TestCacheInvalidation:
    async def test_save_maintenance_invalidates_the_cache(self):
        db = await _new_session(
            AdminMaintenanceSettingsOrmModel(id=1, enabled=False, message="old", allowed_ips=[])
        )
        repo = SqlAlchemyAdminSettingsRepository(db)
        primed = await repo.get_maintenance()
        assert primed.enabled is False

        await repo.save_maintenance(
            AdminMaintenanceSettings(id=1, enabled=True, message="new", allowed_ips=[])
        )

        result = await repo.get_maintenance()
        assert result.enabled is True
        assert result.message == "new"


class TestClearMaintenanceCache:
    async def test_clears_a_primed_cache(self):
        primed = await _new_session(
            AdminMaintenanceSettingsOrmModel(id=1, enabled=True, message=None, allowed_ips=[])
        )
        await SqlAlchemyAdminSettingsRepository(primed).get_maintenance()

        admin_settings_repository.clear_maintenance_cache()

        empty = await _new_session()
        with pytest.raises(RuntimeError):
            await SqlAlchemyAdminSettingsRepository(empty).get_maintenance()
