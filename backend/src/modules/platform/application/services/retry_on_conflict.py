"""Turns a benign numbering race into a retry or a clean 409 instead of a
500.

Numbers are drawn from a counter row per number family and prefix, which
the drawing transaction keeps locked until it ends (number_counters.py), so
two creations never draw the same number. A unique constraint can still
fail when a drawn number is already taken by one that did not come from the
counter, such as a number stored by hand or read from CAD after the
counter's first draw, or when two PDM ingests claim the same CAD part
number. The persistence adapter raises a ConstraintViolationError for every
IntegrityError, and this module tells a numbering conflict apart from any
other violation. A retry draws the next number. Two strategies
exist because not every write can be re-run: commit_with_number_retry
replays a write that is rebuilt entirely from its inputs, and
commit_or_raise_numbering_conflict maps the conflict to a 409 when the
write mutated already-loaded aggregates.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Protocol
from typing import TypeVar

from src.modules.platform.domain.exceptions import NumberingConflictError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import ConstraintViolationError
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

T = TypeVar("T")

# Constraints guarding derived numbers. A conflict on anything else is a
# real error and is never retried. "part_number_registry" matches the
# registry's primary key violation on both Postgres and SQLite.
_NUMBERING_CONSTRAINTS = (
    "production_order_number",
    "lot_number",
    "part_number_registry",
    "uq_made_item_part_number_revision",
    "uq_bought_item_part_number",
    # uq_calculation_document_number_latest, uq_checklist_document_number_latest
    "document_number",
)


class TransactionListener(Protocol):
    """Whatever holds state for the current transaction and must forget it
    after a rollback, such as the lifecycle reconciler's held locks."""

    def transaction_ended(self) -> None: ...


def is_numbering_conflict(error: ConstraintViolationError) -> bool:
    """True only for a violation of one of the constraints above, read from
    the constraint name psycopg reports or, for SQLite, the error text."""
    return any(name in error.constraint for name in _NUMBERING_CONSTRAINTS)


async def commit_with_number_retry(
    uow: IUnitOfWork,
    write: Callable[[], Awaitable[T]],
    attempts: int = 2,
    *,
    reconciler: TransactionListener | None = None,
) -> T:
    """Runs `write()` and commits, retrying after a rollback on a numbering
    conflict up to `attempts` times. `write` must rebuild its whole unit of
    work, since the rollback discards every pending object. A write that
    touches and locks lifecycle rows passes its `reconciler`, which forgets
    them after the rollback, so the retry locks them again instead of
    taking them as held."""
    last_error: ConstraintViolationError | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = await write()
            await uow.commit()
        except ConstraintViolationError as error:
            if not is_numbering_conflict(error):
                raise
            await uow.rollback()
            if reconciler is not None:
                reconciler.transaction_ended()
            last_error = error
            log.warning(
                f"Numbering conflict on attempt {attempt}/{attempts}; "
                f"rolled back and re-deriving the number."
            )
            continue
        else:
            return result
    assert last_error is not None
    raise NumberingConflictError(
        "Could not allocate a unique number after "
        f"{attempts} attempts because of concurrent creations; please retry."
    ) from last_error


async def commit_or_raise_numbering_conflict(uow: IUnitOfWork) -> None:
    """Commits, mapping a numbering conflict to NumberingConflictError (409)
    for writes that cannot be replayed."""
    try:
        await uow.commit()
    except ConstraintViolationError as error:
        if not is_numbering_conflict(error):
            raise
        await uow.rollback()
        raise NumberingConflictError(
            "Could not allocate a unique number because of a concurrent creation; please retry."
        ) from error
