"""
Maps domain exceptions to HTTP status codes and registers the FastAPI
exception handlers that turn a raised DomainError into a JSON response.
"""

import math
from typing import Any
from typing import cast

from fastapi import FastAPI
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm.exc import StaleDataError

from src.modules.platform.domain.exceptions import AuthenticationError
from src.modules.platform.domain.exceptions import BackupAlreadyRunningError
from src.modules.platform.domain.exceptions import BackupError
from src.modules.platform.domain.exceptions import BackupNotConfiguredError
from src.modules.platform.domain.exceptions import BadRequestError
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import ExternalServiceError
from src.modules.platform.domain.exceptions import ForbiddenError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.exceptions import MailRateLimitedError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import PayloadTooLargeError
from src.modules.platform.domain.exceptions import RateLimitedError
from src.modules.platform.domain.exceptions import ServiceUnavailableError
from src.modules.platform.domain.exceptions import ServiceUnreachableError
from src.modules.platform.domain.exceptions import SmtpDeliveryError
from src.modules.platform.domain.exceptions import StorageConnectionError
from src.modules.platform.domain.exceptions import StorageMigrationError
from src.modules.platform.domain.exceptions import StoragePathError
from src.modules.platform.domain.exceptions import UnsupportedFileTypeError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import ConstraintViolationError

# Maps the semantic bases of Platform's domain/exceptions.py to their HTTP
# status, plus the few Platform errors whose status differs from the one
# their base gives them. The errors of other modules inherit these bases,
# so this map never names a module's error. mapped_domain_status walks the
# class chain, so the most derived mapped class wins. A DomainError with no
# mapped class on its chain answers 500.
_STATUS: dict[type[DomainError], int] = {
    BadRequestError: 400,
    AuthenticationError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    PayloadTooLargeError: 413,
    UnsupportedFileTypeError: 415,
    InvalidInputError: 422,
    RateLimitedError: 429,
    ExternalServiceError: 502,
    ServiceUnavailableError: 503,
    # A UserNotFoundError, but answered exactly like a wrong password, so a
    # 404 or 503 cannot reveal a directory outage or which usernames exist.
    CredentialsUnverifiableError: 401,
    # Raised inside backup jobs, which record it on the run row instead.
    BackupError: 500,
    BackupNotConfiguredError: 400,
    BackupAlreadyRunningError: 409,
}

# Errors an operator has to look at, logged as errors instead of warnings.
# The lookup walks the class chain like _STATUS, so every unreachable
# external system is covered through its shared base.
_LOG_ERROR: frozenset[type[DomainError]] = frozenset(
    {
        StorageMigrationError,
        StorageConnectionError,
        StoragePathError,
        ServiceUnreachableError,
    }
)

# Types whose every raise site already logs a better line, so the handler
# skips its own. This is keyed by type, so add a type only if no raise
# site relies on the handler's log.
_SELF_LOGGED: frozenset[type[DomainError]] = frozenset({MailRateLimitedError, SmtpDeliveryError})


def mapped_domain_status(exc: Exception) -> int | None:
    """The status a DomainError maps to through its class chain, or None.
    The Auto-Plan stream uses it to apply the same never-echo rule."""
    return next((_STATUS[k] for k in type(exc).__mro__ if k in _STATUS), None)


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Turns a DomainError into a JSON response. Typed `Exception` only to
    match Starlette's handler signature."""
    # The most derived mapped class wins; None means nothing is mapped.
    mapped = mapped_domain_status(exc)
    status = mapped if mapped is not None else 500
    if type(exc) not in _SELF_LOGGED:
        logs_error = any(k in _LOG_ERROR for k in type(exc).__mro__)
        level = "error" if mapped is None or logs_error else "warning"
        getattr(log, level)("%s: %s", type(exc).__name__, exc)
    # `code` is the class name, so clients never match on the prose. An
    # unmapped exception never echoes its message, which could leak internals.
    detail = str(exc) if mapped is not None else "Internal server error"
    return JSONResponse(
        status_code=status,
        content={"detail": detail, "code": type(exc).__name__},
    )


# query_canceled, raised by the server-side statement_timeout set in
# session.py.
_DB_TIMEOUT_SQLSTATES = frozenset({"57014"})
# lock_not_available, raised by the server-side lock_timeout set in
# session.py: a row lock wait gave up on a concurrent transaction, a lost
# race that a fresh attempt usually wins.
_DB_LOCK_TIMEOUT_SQLSTATES = frozenset({"55P03"})
# deadlock_detected and serialization_failure: the transaction lost a race
# with a concurrent one and was rolled back; repeating the request usually
# succeeds.
_DB_CONFLICT_SQLSTATES = frozenset({"40P01", "40001"})


async def database_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Turns database-side overload into a retryable 503 instead of a
    generic 500: a deadlock or serialization failure, a statement or lock
    wait that hit its server timeout, a lost or refused connection, or no
    pooled connection freeing up within pool_timeout. Nothing about the
    request itself was wrong, so the client is told to retry rather than
    shown an internal error. A lost race of a write that committed nothing,
    a deadlock, a serialization failure or a lock wait that timed out, is
    run once more on the server first (LostRaceRetryMiddleware); this answer
    reaches the client only when that run loses too."""
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate in _DB_CONFLICT_SQLSTATES:
        log.warning("Database conflict (%s): %s", sqlstate, orig)
        detail = "The request collided with another change. Please try again."
        code = "DatabaseConflictError"
    elif sqlstate in _DB_LOCK_TIMEOUT_SQLSTATES:
        log.warning("Database lock timeout (%s): %s", sqlstate, orig)
        detail = "The request waited too long for a record another change holds. Please try again."
        code = "DatabaseLockTimeoutError"
    elif sqlstate in _DB_TIMEOUT_SQLSTATES:
        log.warning("Database timeout (%s): %s", sqlstate, orig)
        detail = "The database took too long to respond. Please try again."
        code = "DatabaseTimeoutError"
    elif isinstance(exc, PoolTimeoutError):
        log.error("Database connection pool exhausted: %s", exc)
        detail = "The server is busy. Please try again."
        code = "DatabaseBusyError"
    else:
        log.error("Database unavailable: %s", exc)
        detail = "The database is currently unavailable. Please try again."
        code = "DatabaseUnavailableError"
    return JSONResponse(status_code=503, content={"detail": detail, "code": code})


async def stale_data_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Answers a write that lost an optimistic version check with 409. A row
    with a version column was changed by another transaction after this
    request read it, so the update matched no row and nothing was written.
    The code is the one ConcurrentModificationError carries, so a client
    handles both the same way: reload and repeat."""
    log.warning("Concurrent modification: %s", exc)
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Someone else changed this record in the meantime. Reload and try again.",
            "code": ConcurrentModificationError.__name__,
        },
    )


async def constraint_violation_handler(_: Request, exc: Exception) -> JSONResponse:
    """Answers a write that broke a database constraint with 409. The checks
    of a use case run before its writes, so a violation that still reaches
    the API means a concurrent change created the conflict, such as a
    duplicate number or a row deleted meanwhile; repeating the request on
    the current state usually succeeds. The constraint is logged, never
    returned, because its name and the statement describe the schema."""
    log.warning("Constraint violation: %s", cast(ConstraintViolationError, exc).constraint)
    return JSONResponse(
        status_code=409,
        content={
            "detail": "This change conflicts with data that changed in the meantime. "
            "Reload and try again.",
            "code": ConflictError.__name__,
        },
    )


def _non_finite_floats_as_text(value: Any) -> Any:
    """Copies encoded JSON data with every NaN or infinite float replaced by
    the token a JSON body spells it with, because the response encoder
    refuses those values."""
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: _non_finite_floats_as_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_non_finite_floats_as_text(item) for item in value]
    return value


async def request_validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Answers a request validation error with the body FastAPI's default
    handler renders, the encoded errors under `detail` with status 422. A
    JSON body may carry NaN or Infinity, which the parser accepts and the
    error echoes under `input` but the response encoder refuses, so those
    values are echoed as text and the client still gets its 422 instead of
    a 500. Typed `Exception` only to match Starlette's handler signature."""
    errors = jsonable_encoder(cast(RequestValidationError, exc).errors())
    return JSONResponse(status_code=422, content={"detail": _non_finite_floats_as_text(errors)})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(OperationalError, database_error_handler)
    app.add_exception_handler(PoolTimeoutError, database_error_handler)
    app.add_exception_handler(StaleDataError, stale_data_error_handler)
    app.add_exception_handler(ConstraintViolationError, constraint_violation_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
