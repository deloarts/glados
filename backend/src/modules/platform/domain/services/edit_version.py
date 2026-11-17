"""
The edit version of a row a user edits in a form, so two people editing the
same row do not overwrite each other. A client reads the row's
`edit_version` and sends it back as `expected_edit_version`; a row that moved
since answers 409 instead of being overwritten.

Lifecycle rows (order, order line, lot, production order, quote request) and
projects move it in their use cases, only on a user edit of an editable
field and on an irreversible action, since their own `version` column also
moves on every derived status and planned date. Master data rows (items,
products, devices, suppliers, customers) move it on every change of a field,
whoever writes it, through the session listener in
`persistence/edit_version_tracking.py`.

The web routes that write such a row's fields require the version, so a
request without it answers 422. A use case checks it only when given,
because the `pat` API keeps it optional and a cascade ends rows the user
never saw.
"""

from typing import Protocol

from src.modules.platform.domain.exceptions import ConcurrentModificationError


class _Versioned(Protocol):
    edit_version: int


def assert_edit_version(row: _Versioned, expected: int | None, *, what: str) -> None:
    """Refuses the write when the client read another edit version of the
    row than it has now. `what` names the row, such as "Order #3"."""
    if expected is not None and expected != row.edit_version:
        raise ConcurrentModificationError(
            f"{what} was changed by someone else since you read it; reload it and try again."
        )


def bump_edit_version(row: _Versioned) -> None:
    row.edit_version += 1
