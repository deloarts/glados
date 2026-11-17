"""
Unit tests for SqlAlchemyEventOutbox.try_lock()/release_lock(): the
dedicated-connection PG advisory xact lock (see advisory_lock.py's
docstring for why a session-level lock leaks through this app's pool) and
its two-phase lifecycle: try_lock() opens and holds a connection across
however long the caller keeps it, release_lock() (called from main.py's
`_open_outbox` in a `finally`, see test_main_outbox_relay_lock.py) ends it.
A fake Session/Engine/Connection stand in for the DB; the real Postgres
lock semantics are proven separately in
tests/integration/test_advisory_lock_postgres.py.
"""

from src.modules.platform.adapters.outbound.persistence.event_outbox import SqlAlchemyEventOutbox


class FakeResult:
    def __init__(self, value: bool) -> None:
        self._value = value

    def scalar(self) -> bool:
        return self._value


class FakeConnection:
    def __init__(self, lock_result: bool = True) -> None:
        self.lock_result = lock_result
        self.began = False
        self.executed: list[tuple[str, dict]] = []
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


class FakeSession:
    """Stands in for the AsyncSession SqlAlchemyEventOutbox is constructed
    with; try_lock() reads the dialect through get_bind() and connects
    through bind."""

    def __init__(self, bind: FakeEngine) -> None:
        self._bind = bind
        self.bind = bind

    def get_bind(self) -> FakeEngine:
        return self._bind


class TestTryLockPostgresql:
    async def test_success_holds_the_connection_open_and_returns_true(self):
        conn = FakeConnection(lock_result=True)
        outbox = SqlAlchemyEventOutbox(FakeSession(FakeEngine("postgresql", conn)))  # type: ignore[arg-type]

        assert await outbox.try_lock() is True
        assert conn.began is True
        assert "idle_in_transaction_session_timeout = 0" in conn.executed[0][0]
        assert "pg_try_advisory_xact_lock" in conn.executed[-1][0]
        assert conn.rolled_back is False  # not released yet; try_lock() keeps it open
        assert conn.closed is False

    async def test_busy_closes_the_connection_immediately_and_returns_false(self):
        conn = FakeConnection(lock_result=False)
        outbox = SqlAlchemyEventOutbox(FakeSession(FakeEngine("postgresql", conn)))  # type: ignore[arg-type]

        assert await outbox.try_lock() is False
        assert conn.rolled_back is True
        assert conn.closed is True


class TestReleaseLock:
    async def test_ends_the_held_connection(self):
        conn = FakeConnection(lock_result=True)
        outbox = SqlAlchemyEventOutbox(FakeSession(FakeEngine("postgresql", conn)))  # type: ignore[arg-type]
        await outbox.try_lock()

        await outbox.release_lock()

        assert conn.rolled_back is True
        assert conn.closed is True

    async def test_is_idempotent(self):
        conn = FakeConnection(lock_result=True)
        outbox = SqlAlchemyEventOutbox(FakeSession(FakeEngine("postgresql", conn)))  # type: ignore[arg-type]
        await outbox.try_lock()
        await outbox.release_lock()
        conn.rolled_back = False  # reset so a second touch would be visible
        conn.closed = False

        await outbox.release_lock()

        assert conn.rolled_back is False
        assert conn.closed is False

    async def test_is_a_no_op_when_try_lock_was_never_called(self):
        conn = FakeConnection()
        outbox = SqlAlchemyEventOutbox(FakeSession(FakeEngine("postgresql", conn)))  # type: ignore[arg-type]

        await outbox.release_lock()  # must not raise

        assert conn.rolled_back is False
        assert conn.closed is False

    async def test_is_a_no_op_when_try_lock_found_it_busy(self):
        conn = FakeConnection(lock_result=False)
        outbox = SqlAlchemyEventOutbox(FakeSession(FakeEngine("postgresql", conn)))  # type: ignore[arg-type]
        await outbox.try_lock()
        conn.rolled_back = (
            False  # try_lock's own busy-path already closed it; reset to detect a re-touch
        )
        conn.closed = False

        await outbox.release_lock()

        assert conn.rolled_back is False
        assert conn.closed is False


class TestSqliteDialect:
    async def test_try_lock_returns_true_without_opening_a_connection(self):
        engine = FakeEngine("sqlite", connection=None)
        outbox = SqlAlchemyEventOutbox(FakeSession(engine))  # type: ignore[arg-type]

        assert await outbox.try_lock() is True
        assert engine.connect_calls == 0

    async def test_release_lock_is_a_no_op(self):
        engine = FakeEngine("sqlite", connection=None)
        outbox = SqlAlchemyEventOutbox(FakeSession(engine))  # type: ignore[arg-type]
        await outbox.try_lock()

        await outbox.release_lock()  # must not raise

        assert engine.connect_calls == 0
