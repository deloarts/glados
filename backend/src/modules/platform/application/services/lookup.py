"""
found_or_raise turns the optional result of a repository read into the
entity or a not-found domain error, so a use case loads what it needs in one
line. The caller passes the error class and the full message, which keeps
every error text exactly as the use case words it. The check is `is None`,
because a repository read returns either an entity or None and entities are
always truthy.
"""

from collections.abc import Callable

from src.modules.platform.domain.exceptions import DomainError


def found_or_raise[T](entity: T | None, error: Callable[[str], DomainError], message: str) -> T:
    """Return `entity`, or raise `error(message)` when it is None."""
    if entity is None:
        raise error(message)
    return entity
