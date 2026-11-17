"""
fetch_all walks a paged repository read to the end, for the callers that
need every row rather than one page, such as a lookup list or a broadcast.
The repositories clamp an oversized limit, so a caller cannot ask for
everything in one call. The walk keeps the order the page function returns
its rows in; a caller that needs a stable order across pages passes a page
function that sorts.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


async def fetch_all(
    page: Callable[[int, int], Awaitable[tuple[int, Sequence[T]]]], page_size: int
) -> list[T]:
    """Calls `page(skip, limit)` until it returns an empty page or `skip`
    reaches the total it reports, and returns every row in order. `skip`
    advances by the rows actually returned, so a repository that clamps
    `page_size` lower still yields every row."""
    items: list[T] = []
    skip = 0
    while True:
        total, batch = await page(skip, page_size)
        items.extend(batch)
        skip += len(batch)
        if not batch or skip >= total:
            break
    return items
