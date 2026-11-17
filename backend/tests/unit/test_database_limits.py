"""
The connection parameters that carry the server-side database timeouts
(session.py) and the 503 mapping for the errors those timeouts and an
exhausted pool raise (exception_handlers.database_error_handler).
"""

import json

from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from src.modules.platform.adapters.inbound.api.exception_handlers import database_error_handler
from src.modules.platform.adapters.outbound.persistence.session import postgres_connect_args
from src.modules.platform.infrastructure.config.settings import DatabaseSettings


def _settings(**overrides: int) -> DatabaseSettings:
    return DatabaseSettings(
        url="postgresql://u:p@db:5432/glados",
        **overrides,
    )


def test_connect_args_carry_all_three_timeouts() -> None:
    args = postgres_connect_args(_settings(), "glados-host-1")

    assert args["options"] == (
        "-c statement_timeout=30s -c lock_timeout=5s -c idle_in_transaction_session_timeout=60s"
    )
    assert args["application_name"] == "glados-host-1"


def test_connect_args_follow_settings_and_zero_disables() -> None:
    args = postgres_connect_args(
        _settings(
            statement_timeout_seconds=0,
            lock_timeout_seconds=2,
            idle_in_transaction_timeout_seconds=60,
        ),
        "x",
    )

    assert args["options"] == (
        "-c statement_timeout=0s -c lock_timeout=2s -c idle_in_transaction_session_timeout=60s"
    )


def test_application_name_is_capped_at_the_postgres_limit() -> None:
    assert len(postgres_connect_args(_settings(), "g" * 100)["application_name"]) == 63


class _DriverError(Exception):
    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("driver error")
        self.sqlstate = sqlstate


async def _handle(exc: Exception) -> tuple[int, dict[str, str]]:
    response = await database_error_handler(None, exc)  # type: ignore[arg-type]
    return response.status_code, json.loads(bytes(response.body))


async def test_statement_timeout_is_a_retryable_503(glados_caplog) -> None:
    status, body = await _handle(OperationalError("SELECT 1", None, _DriverError("57014")))

    assert status == 503
    assert body["code"] == "DatabaseTimeoutError"


async def test_lock_timeout_is_a_lost_race_the_server_retries(glados_caplog) -> None:
    """A row lock wait that gave up on a concurrent transaction is a lost
    race, answered with the code LostRaceRetryMiddleware runs once more."""
    status, body = await _handle(OperationalError("SELECT 1", None, _DriverError("55P03")))

    assert status == 503
    assert body["code"] == "DatabaseLockTimeoutError"


async def test_deadlock_is_a_retryable_conflict(glados_caplog) -> None:
    status, body = await _handle(OperationalError("UPDATE x", None, _DriverError("40P01")))

    assert status == 503
    assert body["code"] == "DatabaseConflictError"


async def test_serialization_failure_is_a_retryable_conflict(glados_caplog) -> None:
    status, body = await _handle(OperationalError("UPDATE x", None, _DriverError("40001")))

    assert status == 503
    assert body["code"] == "DatabaseConflictError"


async def test_lost_connection_is_a_503_without_driver_detail(glados_caplog) -> None:
    status, body = await _handle(OperationalError("SELECT 1", None, _DriverError(None)))

    assert status == 503
    assert body["code"] == "DatabaseUnavailableError"
    assert "driver error" not in body["detail"]


async def test_exhausted_pool_is_a_503(glados_caplog) -> None:
    status, body = await _handle(PoolTimeoutError("QueuePool limit reached"))

    assert status == 503
    assert body["code"] == "DatabaseBusyError"
