"""
Shared helper for repository get_multi() filter building. One `if
filters.x: q = q.where(...)` branch per filter drives a get_multi()'s
cognitive complexity into the 30s and 40s, so apply_filters() collects the
same branches into a flat list of filter specs applied in a single loop
instead, one spec per filter, independent of how many filters a given
repository has.

A spec carries the raw filter value and a clause builder that receives the
value once the filter is active, so the builder sees it narrowed to its
non-None type. `when()` and `when_not_none()` build the specs and tie the
builder's parameter to the value's type. The builder runs only for an
active filter, since some clauses (an `.in_()` over a possibly-None or
empty sequence, a correlated EXISTS subquery) are only valid to construct
once the filter's value has been checked.
"""

from collections.abc import Callable
from collections.abc import Iterable
from typing import Any
from typing import NamedTuple
from typing import TypeVar

from sqlalchemy import ColumnElement
from sqlalchemy import Select

_T = TypeVar("_T")
_Q = TypeVar("_Q", bound="Select[Any]")


class FilterSpec(NamedTuple):
    """One filter: whether it applies, its value, and the builder that turns
    the value into its clause. Built by `when()` or `when_not_none()`."""

    active: bool
    value: object
    build_clause: Callable[[Any], "ColumnElement[bool]"]


def when(value: _T | None, build_clause: Callable[[_T], "ColumnElement[bool]"]) -> FilterSpec:
    """A filter applied when `value` is truthy, so None, an empty list and an
    empty string leave it out."""
    return FilterSpec(bool(value), value, build_clause)


def when_not_none(
    value: _T | None, build_clause: Callable[[_T], "ColumnElement[bool]"]
) -> FilterSpec:
    """A filter applied whenever `value` is not None, for a value such as
    False or 0 that still filters."""
    return FilterSpec(value is not None, value, build_clause)


def apply_filters(query: _Q, specs: Iterable[FilterSpec]) -> _Q:
    """Applies each active spec as its own `.where()` call, in order,
    skipping the rest. Equivalent to a chain of `if filters.x: query =
    query.where(...)` statements, minus the per-filter branch."""
    for active, value, build_clause in specs:
        if active:
            query = query.where(build_clause(value))
    return query
