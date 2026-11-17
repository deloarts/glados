"""
Unit coverage for src/modules/platform/adapters/inbound/api/readiness.py: the pieces
tests/integration/test_api_readiness.py can't reach, since that suite
monkeypatches check_database/check_redis wholesale to assert on /ready's
HTTP contract rather than on these functions' own bodies.
"""

import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from src.modules.platform.adapters.inbound.api import readiness


class TestCheckDatabase:
    async def test_executes_select_1_through_sessionlocal(self, monkeypatch):
        """Same style as the repository unit tests (grep tests/unit for
        `create_async_engine("sqlite+aiosqlite://")`): a real, throwaway
        SQLite session factory swapped in for SessionLocal, with a
        cursor-level listener recording every statement actually sent to
        the DBAPI."""
        engine = create_async_engine("sqlite+aiosqlite://")
        statements: list[str] = []

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def _capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        monkeypatch.setattr(readiness, "SessionLocal", async_sessionmaker(engine))

        await readiness.check_database()  # must not raise
        await engine.dispose()

        assert any("SELECT 1" in statement for statement in statements)


class TestReadinessRedisClientFactory:
    def setup_method(self) -> None:
        readiness._get_readiness_redis_client.cache_clear()

    def teardown_method(self) -> None:
        readiness._get_readiness_redis_client.cache_clear()

    def test_client_carries_the_one_second_socket_timeouts(self):
        """The whole reason for a dedicated client instead of reusing
        get_async_redis_client() (src/modules/platform/infrastructure/redis_client.py, whose
        timeouts and retry are sized for application traffic): a hung Redis
        must fail this probe within one second, not hang it."""
        client = readiness._get_readiness_redis_client()

        kwargs = client.connection_pool.connection_kwargs
        assert kwargs["socket_connect_timeout"] == 1
        assert kwargs["socket_timeout"] == 1

    def test_client_is_cached_across_calls(self):
        first = readiness._get_readiness_redis_client()
        second = readiness._get_readiness_redis_client()

        assert first is second


async def _ok() -> None:
    return None


class TestReadinessReport:
    async def test_all_ok_when_both_checks_pass(self, monkeypatch):
        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        all_ok, checks = await readiness.readiness_report()

        assert all_ok is True
        assert checks == {"database": "ok", "redis": "ok"}

    async def test_a_failing_database_check_is_caught_and_reported_alone(self, monkeypatch):
        async def _boom():
            raise RuntimeError("db is down")

        monkeypatch.setattr(readiness, "check_database", _boom)
        monkeypatch.setattr(readiness, "check_redis", _ok)

        all_ok, checks = await readiness.readiness_report()

        assert all_ok is False
        assert checks == {"database": "fail", "redis": "ok"}

    async def test_a_failing_redis_check_is_caught_and_reported_alone(self, monkeypatch):
        async def _boom():
            raise RuntimeError("redis is down")

        monkeypatch.setattr(readiness, "check_database", _ok)
        monkeypatch.setattr(readiness, "check_redis", _boom)

        all_ok, checks = await readiness.readiness_report()

        assert all_ok is False
        assert checks == {"database": "ok", "redis": "fail"}

    async def test_logs_a_warning_naming_the_failed_component(self, monkeypatch, glados_caplog):
        async def _boom():
            raise ValueError("nope")

        monkeypatch.setattr(readiness, "check_database", _boom)
        monkeypatch.setattr(readiness, "check_redis", _ok)
        glados_caplog.set_level(logging.WARNING, logger="glados")

        await readiness.readiness_report()

        warnings = [r for r in glados_caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "database" in warnings[0].getMessage()
        assert warnings[0].exc_info is not None
