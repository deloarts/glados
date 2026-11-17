"""
A bare list request must not return the entire table, yet `skip`/
`limit` default to `None` in every FilterDto, and `Query.limit(None)`
is a no-op in SQLAlchemy, not "zero rows". Endpoint-side `Query(...,
le=MAX_PAGE_SIZE)` validation rejects an explicit over-limit request on
most list endpoints, but does nothing for an *omitted* limit, the common
case.
clamp_page is the repository-side backstop: every get_multi should call
it before building its query, so omission and validation-bypass are
closed the same way, in one place, regardless of what the endpoint layer
does or doesn't enforce.
"""

from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE


def clamp_page(
    skip: int | None, limit: int | None, *, min_limit: int | None = None
) -> tuple[int, int]:
    """Normalizes raw filter values into a safe (skip, limit) pair, defaulting and capping
    both to DEFAULT_PAGE_SIZE and MAX_PAGE_SIZE.

    `min_limit`, when given, raises what an omitted/non-positive `limit`
    resolves to above DEFAULT_PAGE_SIZE (still capped by MAX_PAGE_SIZE), for
    get_multi callers whose FilterDto carries an `ids` field
    documented as "live row-sync: refetch specific rows, ignore paging".
    Those callers pass `len(filters.ids)` here so a caller that only sets
    `ids` (no explicit `limit`) gets every matching row back instead of
    silently truncating to DEFAULT_PAGE_SIZE once `ids` exceeds it, since the
    query is already scoped to that specific, bounded id set, so there is
    no unbounded-table risk clamp_page exists to prevent. An explicitly
    provided `limit` is never overridden by `min_limit`."""
    safe_skip = skip if skip is not None and skip > 0 else 0
    if limit is not None and limit > 0:
        safe_limit = limit
    else:
        safe_limit = DEFAULT_PAGE_SIZE
        if min_limit is not None and min_limit > safe_limit:
            safe_limit = min_limit
    return safe_skip, min(safe_limit, MAX_PAGE_SIZE)
