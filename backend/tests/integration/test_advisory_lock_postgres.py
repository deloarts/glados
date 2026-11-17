"""
Opt-in integration test for advisory_lock() against a real Postgres. It is
skipped unless GLADOS_TEST_PG_URL is set, and that variable must name an
empty throwaway database, never the development one, because the same
variable drives tests/pg and test_migrations_postgres.py, which create and
drop tables (docs/reference/development-testing.md). The default suite runs on
SQLite only. This file uses its own engine, creates no tables and leaves no
rows; it only exercises pg_locks.

The rest of the suite can never exercise pg_try_advisory_xact_lock, and the
fake-connection unit test (test_advisory_lock.py) proves that the right SQL
is sent, not that Postgres's lock semantics behave the way that SQL claims.
This test covers the second part.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine

from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock

_PG_URL = os.environ.get("GLADOS_TEST_PG_URL")

pytestmark = pytest.mark.skipif(
    not _PG_URL, reason="set GLADOS_TEST_PG_URL to a real Postgres to run this test"
)

# Arbitrary, and deliberately NOT any of the app's real lock keys
# (AdvisoryLockKey); this suite must never contend with, or be confused by,
# whatever the actual application is doing with those.
_KEY = 0x0BADF00D


@pytest.fixture
async def pg_engine():
    assert _PG_URL is not None
    engine = create_async_engine(_PG_URL)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _lock_row_count(engine: AsyncEngine, key: int) -> int:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = :key"),
                {"key": key},
            )
        ).scalar()


class TestTwoConnectionsRaceForTheSameKey:
    async def test_first_locks_second_does_not_third_does_after_first_exits(self, pg_engine):
        async with advisory_lock(pg_engine, _KEY) as first_locked:
            assert first_locked is True

            async with advisory_lock(pg_engine, _KEY) as second_locked:
                assert second_locked is False  # first connection still holds it

        # first's `with` has exited -> the xact ended -> the key is free
        async with advisory_lock(pg_engine, _KEY) as third_locked:
            assert third_locked is True


class TestLockDoesNotSurviveContextExitThroughThePool:
    async def test_no_advisory_lock_row_remains_after_a_normal_exit(self, pg_engine):
        async with advisory_lock(pg_engine, _KEY):
            assert await _lock_row_count(pg_engine, _KEY) == 1  # held while inside the block

        assert await _lock_row_count(pg_engine, _KEY) == 0

    async def test_no_advisory_lock_row_remains_after_the_body_raises(self, pg_engine):
        with pytest.raises(RuntimeError):
            async with advisory_lock(pg_engine, _KEY):
                raise RuntimeError("simulated failure inside the locked block")

        assert await _lock_row_count(pg_engine, _KEY) == 0

    async def test_reusing_the_engine_repeatedly_never_accumulates_locks(self, pg_engine):
        """The case this whole module exists to guard: taking and
        releasing the same key many times through the SAME pooled engine
        (i.e. whatever connection the pool happens to hand back) must never
        leave more than the one lock genuinely held at any instant. A
        session-level pg_try_advisory_lock would leak a lock into the pool
        on every single call (see advisory_lock.py's docstring)."""
        for _ in range(5):
            async with advisory_lock(pg_engine, _KEY) as locked:
                assert locked is True

        assert await _lock_row_count(pg_engine, _KEY) == 0
