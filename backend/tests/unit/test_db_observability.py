"""
The pool gauge follows checkouts and checkins, and statements over the
slow-query threshold are counted and logged without their parameters.
"""

from sqlalchemy import create_engine
from sqlalchemy import text

from src.modules.platform.adapters.outbound.persistence.db_observability import DB_POOL_CHECKED_OUT
from src.modules.platform.adapters.outbound.persistence.db_observability import DB_SLOW_QUERIES
from src.modules.platform.adapters.outbound.persistence.db_observability import (
    register_db_observability,
)


def _value(metric) -> float:
    return metric._value.get()


def test_pool_gauge_follows_checkout_and_checkin() -> None:
    engine = create_engine("sqlite://")
    register_db_observability(engine, slow_query_threshold_ms=0)
    before = _value(DB_POOL_CHECKED_OUT)

    with engine.connect() as conn:
        assert _value(DB_POOL_CHECKED_OUT) == before + 1
        conn.execute(text("SELECT 1"))
    assert _value(DB_POOL_CHECKED_OUT) == before


def test_slow_statements_are_counted_and_logged_without_parameters(glados_caplog) -> None:
    engine = create_engine("sqlite://")
    # Every statement counts as slow at a 1 ms threshold with a sleeping function.
    register_db_observability(engine, slow_query_threshold_ms=1)
    before = _value(DB_SLOW_QUERIES)

    with engine.connect() as conn:
        conn.connection.driver_connection.create_function(  # type: ignore[union-attr]
            "nap", 1, lambda s: __import__("time").sleep(s) or 1
        )
        conn.execute(text("SELECT nap(:seconds)"), {"seconds": 0.01})

    assert _value(DB_SLOW_QUERIES) == before + 1
    messages = [r.getMessage() for r in glados_caplog.records if "Slow query" in r.getMessage()]
    assert messages and "SELECT nap(?)" in messages[0]
    assert "0.01" not in messages[0]


def test_zero_threshold_disables_the_slow_query_log() -> None:
    engine = create_engine("sqlite://")
    register_db_observability(engine, slow_query_threshold_ms=0)
    before = _value(DB_SLOW_QUERIES)

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    assert _value(DB_SLOW_QUERIES) == before
