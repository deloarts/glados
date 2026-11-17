"""
Unit tests for fetch_all (src/modules/platform/application/services/paging.py), which walks
a paged repository read to its end.
"""

from src.modules.platform.application.services.paging import fetch_all


class _PagedRows:
    """Serves `rows` in pages, clamping the limit to `clamp` the way the
    repositories clamp an oversized page."""

    def __init__(self, rows: list[int], clamp: int | None = None) -> None:
        self._rows = rows
        self._clamp = clamp
        self.calls: list[tuple[int, int]] = []

    async def page(self, skip: int, limit: int) -> tuple[int, list[int]]:
        self.calls.append((skip, limit))
        size = min(limit, self._clamp) if self._clamp is not None else limit
        return len(self._rows), self._rows[skip : skip + size]


async def test_fetch_all_returns_every_row_in_order_across_pages():
    source = _PagedRows(list(range(7)))

    rows = await fetch_all(source.page, 3)

    assert rows == list(range(7))
    assert source.calls == [(0, 3), (3, 3), (6, 3)]


async def test_fetch_all_stops_after_one_call_on_an_empty_table():
    source = _PagedRows([])

    assert await fetch_all(source.page, 3) == []
    assert source.calls == [(0, 3)]


async def test_fetch_all_advances_by_the_rows_returned_when_the_limit_is_clamped():
    source = _PagedRows(list(range(5)), clamp=2)

    rows = await fetch_all(source.page, 10)

    assert rows == list(range(5))
    assert [skip for skip, _ in source.calls] == [0, 2, 4]


async def test_fetch_all_stops_on_an_empty_page_even_if_the_total_is_higher():
    async def page(skip: int, limit: int) -> tuple[int, list[int]]:
        return 100, [1, 2] if skip == 0 else []

    assert await fetch_all(page, 2) == [1, 2]
