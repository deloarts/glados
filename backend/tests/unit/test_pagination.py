"""
Coverage for src/modules/platform/adapters/outbound/persistence/pagination.py's clamp_page,
the repository-side backstop against a bare list request (limit omitted)
returning an entire table.
"""

from src.modules.platform.adapters.outbound.persistence.pagination import clamp_page
from src.modules.platform.const import DEFAULT_PAGE_SIZE
from src.modules.platform.const import MAX_PAGE_SIZE


class TestClampPage:
    def test_both_none_uses_the_defaults(self):
        assert clamp_page(None, None) == (0, DEFAULT_PAGE_SIZE)

    def test_omitted_limit_does_not_mean_unbounded(self):
        _skip, limit = clamp_page(0, None)
        assert limit == DEFAULT_PAGE_SIZE

    def test_within_bounds_passes_through(self):
        assert clamp_page(20, 50) == (20, 50)

    def test_over_the_cap_is_clamped(self):
        _, limit = clamp_page(0, MAX_PAGE_SIZE + 1000)
        assert limit == MAX_PAGE_SIZE

    def test_exactly_the_cap_is_unchanged(self):
        _, limit = clamp_page(0, MAX_PAGE_SIZE)
        assert limit == MAX_PAGE_SIZE

    def test_negative_skip_becomes_zero(self):
        skip, _ = clamp_page(-5, 10)
        assert skip == 0

    def test_zero_or_negative_limit_falls_back_to_the_default(self):
        assert clamp_page(0, 0)[1] == DEFAULT_PAGE_SIZE
        assert clamp_page(0, -1)[1] == DEFAULT_PAGE_SIZE


class TestClampPageMinLimit:
    """min_limit exists for the `ids` filter: a FilterDto whose
    `ids` field is documented "live row-sync: refetch specific rows,
    ignore paging" (OrderFilterDto, MadeItemDemandFilterDto, LotFilterDto,
    SourceItemDemandFilterDto, DemandItemFilterDto) must return every
    matching row when the caller only sets `ids` and omits `limit`, not
    silently truncate to DEFAULT_PAGE_SIZE once `ids` has more entries
    than that."""

    def test_omitted_limit_with_min_limit_above_default_uses_min_limit(self):
        skip, limit = clamp_page(None, None, min_limit=150)
        assert (skip, limit) == (0, 150)

    def test_omitted_limit_with_min_limit_below_default_keeps_the_default(self):
        # DEFAULT_PAGE_SIZE is still a floor: a handful of ids should not
        # shrink the effective limit below the ordinary default.
        skip, limit = clamp_page(None, None, min_limit=3)
        assert (skip, limit) == (0, DEFAULT_PAGE_SIZE)

    def test_min_limit_is_still_capped_at_the_page_max(self):
        _, limit = clamp_page(None, None, min_limit=MAX_PAGE_SIZE + 1000)
        assert limit == MAX_PAGE_SIZE

    def test_explicit_limit_overrides_min_limit(self):
        # "an explicitly provided limit should still be honored": a
        # caller that sets both `ids` and its own `limit` (e.g. a smaller
        # page over a larger id set) must not be overridden.
        skip, limit = clamp_page(0, 10, min_limit=150)
        assert (skip, limit) == (0, 10)

    def test_zero_or_negative_limit_still_falls_back_to_min_limit(self):
        # An explicit but non-positive limit is treated the same as
        # omitted (see the base zero/negative test above), min_limit
        # still applies.
        assert clamp_page(0, 0, min_limit=150)[1] == 150
        assert clamp_page(0, -1, min_limit=150)[1] == 150

    def test_no_min_limit_behaves_exactly_like_before(self):
        assert clamp_page(None, None, min_limit=None) == clamp_page(None, None)
