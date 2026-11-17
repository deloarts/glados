"""Translates SQLAlchemy's IntegrityError into the port-level
ConstraintViolationError for every statement an engine runs.

The translation happens in the engine's handle_error hook, so it covers a
flush inside any repository call as well as the commit itself. The raised
SqlConstraintViolationError is both an IntegrityError and a
ConstraintViolationError: adapter code and tests that catch IntegrityError
keep working, while the application layer catches the port type.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine import ExceptionContext
from sqlalchemy.exc import IntegrityError

from src.modules.platform.ports.outbound.unit_of_work_port import ConstraintViolationError


def violated_constraint(orig: BaseException | None) -> str:
    """The constraint name from psycopg's diagnostics, or the driver's
    message when the driver exposes no structured name (SQLite)."""
    constraint_name = getattr(getattr(orig, "diag", None), "constraint_name", None)
    return constraint_name if constraint_name else str(orig)


class SqlConstraintViolationError(IntegrityError, ConstraintViolationError):
    """An IntegrityError that also carries the port-level constraint."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        IntegrityError.__init__(self, *args, **kwargs)
        # The cooperative init chain hands ConstraintViolationError the
        # rendered message, so the constraint is set once the chain is done.
        self.constraint = violated_constraint(self.orig)


def _translate(context: ExceptionContext) -> BaseException | None:
    error = context.sqlalchemy_exception
    if not isinstance(error, IntegrityError) or isinstance(error, SqlConstraintViolationError):
        return None
    if error.orig is None:
        return None
    return SqlConstraintViolationError(
        error.statement,
        error.params,
        error.orig,
        hide_parameters=error.hide_parameters,
        connection_invalidated=error.connection_invalidated,
        code=error.__dict__.get("code"),
        ismulti=error.ismulti,
    )


def register_constraint_violation_translation(sync_engine: Engine) -> None:
    """Attaches the translation to an engine (the sync facade of an async
    engine)."""
    event.listen(sync_engine, "handle_error", _translate, retval=True)
