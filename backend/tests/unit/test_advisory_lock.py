"""
Unit tests for advisory_lock() with a fake AsyncEngine/AsyncConnection: proves the
right calls happen in the right order (connect -> begin -> the xact-lock
SQL -> rollback -> close, always, even when the `async with` body raises) and
that a non-postgresql dialect never opens a connection at all. What this
CANNOT prove is that pg_try_advisory_xact_lock actually behaves the way
these calls assume against a real server, see
tests/integration/test_advisory_lock_postgres.py for that (opt-in, needs a
real Postgres).
"""

import pytest

from src.modules.external_data.adapters.outbound.persistence.pdm_file_lock import pdm_file_lock_key
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.advisory_lock import advisory_lock


class FakeResult:
    def __init__(self, value: bool) -> None:
        self._value = value

    def scalar(self) -> bool:
        return self._value


class FakeConnection:
    def __init__(self, lock_result: bool = True) -> None:
        self.lock_result = lock_result
        self.executed: list[tuple[str, dict]] = []
        self.began = False
        self.rolled_back = False
        self.closed = False

    async def begin(self) -> None:
        self.began = True

    async def execute(self, stmt: object, params: dict | None = None) -> FakeResult:
        self.executed.append((str(stmt), params or {}))
        return FakeResult(self.lock_result)

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


class FakeDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeEngine:
    def __init__(self, dialect_name: str, connection: FakeConnection | None = None) -> None:
        self.dialect = FakeDialect(dialect_name)
        self._connection = connection
        self.connect_calls = 0

    async def connect(self) -> FakeConnection:
        self.connect_calls += 1
        assert self._connection is not None
        return self._connection


KEY = 0x1234


class TestPostgresqlDialect:
    async def test_executes_the_xact_lock_statement_with_the_key(self):
        conn = FakeConnection(lock_result=True)
        engine = FakeEngine("postgresql", conn)

        async with advisory_lock(engine, KEY) as locked:
            assert locked is True

        assert conn.began is True
        assert "idle_in_transaction_session_timeout = 0" in conn.executed[0][0]
        (sql, params) = conn.executed[-1]
        assert "pg_try_advisory_xact_lock" in sql
        assert params == {"key": KEY}

    async def test_lock_busy_yields_false(self):
        conn = FakeConnection(lock_result=False)
        engine = FakeEngine("postgresql", conn)

        async with advisory_lock(engine, KEY) as locked:
            assert locked is False

    async def test_connection_is_rolled_back_and_closed_on_normal_exit(self):
        conn = FakeConnection()
        engine = FakeEngine("postgresql", conn)

        async with advisory_lock(engine, KEY):
            assert conn.rolled_back is False  # not yet, still inside the block
            assert conn.closed is False

        assert conn.rolled_back is True
        assert conn.closed is True

    async def test_connection_is_rolled_back_and_closed_when_the_body_raises(self):
        conn = FakeConnection()
        engine = FakeEngine("postgresql", conn)

        with pytest.raises(RuntimeError, match="boom"):
            async with advisory_lock(engine, KEY):
                raise RuntimeError("boom")

        assert conn.rolled_back is True
        assert conn.closed is True

    async def test_a_new_connection_is_opened_each_call(self):
        conn = FakeConnection()
        engine = FakeEngine("postgresql", conn)

        async with advisory_lock(engine, KEY):
            pass
        async with advisory_lock(engine, KEY):
            pass

        assert engine.connect_calls == 2


class TestNonPostgresqlDialect:
    async def test_sqlite_yields_true_without_opening_a_connection(self):
        engine = FakeEngine("sqlite", connection=None)

        async with advisory_lock(engine, KEY) as locked:
            assert locked is True

        assert engine.connect_calls == 0


class TestAdvisoryLockKeys:
    def test_every_key_is_unique(self):
        """An IntEnum turns a repeated value into a silent alias, so two lock
        sites would share one key; this counts the declared names instead."""
        values = [member.value for member in AdvisoryLockKey.__members__.values()]

        assert len(values) == len(set(values))

    def test_a_per_file_key_never_meets_a_single_key_lock(self):
        single_keys = {int(member) for member in AdvisoryLockKey}

        assert all(key < 2**32 for key in single_keys)
        assert pdm_file_lock_key(0) >= 2**32
        assert pdm_file_lock_key(0xFFFFFFFF) not in single_keys
