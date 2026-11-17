"""
Unit tests for the part-number registry (docs/FIELD_OWNERSHIP.md
principle 2): claim/assert_family/release_if_unused semantics and the
shared next_part_number sequence, exercised against a small in-memory
implementation of IPartNumberRegistry so these run with no database. The
same behaviour is proven against the real SQLAlchemy adapter in
tests/integration/test_part_number_registry_repository.py.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.errors import PartNumberInUseError
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.platform.domain.services.numbering_format import render_prefix
from src.shared_kernel.domain.services.clock import today_utc


class InMemoryPartNumberRegistry:
    """Mirrors IPartNumberRegistry exactly (the interface this test suite
    is really specifying), so a future adapter swap has this behaviour
    pinned independent of any database."""

    def __init__(self) -> None:
        self._entries: dict[str, str] = {}

    @property
    def entries(self) -> dict[str, str]:
        """Each claimed part number with the kind it is claimed for, for assertions."""
        return self._entries

    async def owner_of(self, part_number: str) -> PartNumberRegistryEntry | None:
        kind = self._entries.get(part_number)
        if kind is None:
            return None
        return PartNumberRegistryEntry(
            part_number=part_number, kind=ItemKind(kind), created=datetime(2026, 1, 1, tzinfo=UTC)
        )

    async def claim(self, part_number: str, kind: str) -> None:
        existing = self._entries.get(part_number)
        if existing is not None:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing!r}."
            )
        self._entries[part_number] = kind

    async def assert_family(self, part_number: str, kind: str) -> None:
        existing = self._entries.get(part_number)
        if existing is None:
            await self.claim(part_number, kind)
            return
        if existing != kind:
            raise PartNumberInUseError(
                f"Part number {part_number!r} is already registered to {existing!r}."
            )

    async def release_if_unused(self, part_number: str) -> None:
        self._entries.pop(part_number, None)

    async def next_part_number(self, template: str) -> str:
        prefix, width = render_prefix(template, today=today_utc())
        candidates = [
            int(pn[len(prefix) :])
            for pn in self._entries
            if pn.startswith(prefix) and pn[len(prefix) :].isdigit()
        ]
        seq = max(candidates) + 1 if candidates else 1
        return f"{prefix}{str(seq).zfill(width)}"


class TestClaim:
    async def test_claims_a_new_number(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "made")
        assert registry.entries["PN-1"] == "made"

    async def test_duplicate_within_same_kind_raises(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "made")
        with pytest.raises(PartNumberInUseError):
            await registry.claim("PN-1", "made")

    async def test_duplicate_across_kinds_raises(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "made")
        with pytest.raises(PartNumberInUseError):
            await registry.claim("PN-1", "bought")

    async def test_error_names_the_owning_kind(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "bought")
        with pytest.raises(PartNumberInUseError, match="bought"):
            await registry.claim("PN-1", "made")

    async def test_distinct_numbers_do_not_conflict(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "made")
        await registry.claim("PN-2", "bought")  # no raise

        assert registry.entries == {"PN-1": "made", "PN-2": "bought"}


class TestOwnerOf:
    async def test_returns_none_for_an_unclaimed_number(self):
        registry = InMemoryPartNumberRegistry()
        assert await registry.owner_of("PN-1") is None

    async def test_returns_the_owning_kind_without_claiming_anything(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "bought")
        entry = await registry.owner_of("PN-1")
        assert entry is not None
        assert entry.part_number == "PN-1"
        assert entry.kind == "bought"
        # A read, not a claim: calling it again must not raise or change
        # anything, unlike claim()/assert_family().
        assert (await registry.owner_of("PN-1")).kind == "bought"  # type: ignore[union-attr]


class TestAssertFamily:
    async def test_passes_for_same_kind(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "made")
        await registry.assert_family("PN-1", "made")  # no raise
        assert registry.entries["PN-1"] == "made"

    async def test_claims_when_missing(self):
        registry = InMemoryPartNumberRegistry()
        await registry.assert_family("PN-1", "made")
        assert registry.entries["PN-1"] == "made"

    async def test_raises_for_other_kind(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "bought")
        with pytest.raises(PartNumberInUseError):
            await registry.assert_family("PN-1", "made")

    async def test_a_missing_entry_registered_by_assert_family_stays_claimed(self):
        """A revision family that reaches assert_family for the first
        time (e.g. a family whose first row predates the backfill) is
        claimed exactly once: a second sibling revision under the same
        kind must not re-raise."""
        registry = InMemoryPartNumberRegistry()
        await registry.assert_family("PN-1", "made")
        await registry.assert_family("PN-1", "made")  # no raise, still one entry
        assert registry.entries == {"PN-1": "made"}


class TestReleaseIfUnused:
    async def test_removes_entry(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("PN-1", "made")
        await registry.release_if_unused("PN-1")
        assert "PN-1" not in registry.entries

    async def test_missing_entry_is_a_no_op(self):
        registry = InMemoryPartNumberRegistry()
        await registry.release_if_unused("PN-1")  # no raise

        assert registry.entries == {}


class TestNextPartNumber:
    async def test_first_number_starts_at_one(self):
        registry = InMemoryPartNumberRegistry()
        assert await registry.next_part_number("MADE-{seq:04d}") == "MADE-0001"

    async def test_increments_after_a_claim(self):
        registry = InMemoryPartNumberRegistry()
        first = await registry.next_part_number("PN-{seq:04d}")
        await registry.claim(first, "made")
        assert await registry.next_part_number("PN-{seq:04d}") == "PN-0002"

    async def test_shared_sequence_across_kinds(self):
        """A made-item family and a bought item drawing from the same
        template consume one sequence, not two, which is the whole point of
        the registry existing as a table separate from either item table."""
        registry = InMemoryPartNumberRegistry()
        first = await registry.next_part_number("PN-{seq:04d}")
        await registry.claim(first, "made")
        second = await registry.next_part_number("PN-{seq:04d}")
        assert second == "PN-0002"
        await registry.claim(second, "bought")
        third = await registry.next_part_number("PN-{seq:04d}")
        assert third == "PN-0003"

    async def test_different_templates_do_not_interfere(self):
        registry = InMemoryPartNumberRegistry()
        await registry.claim("MADE-0001", "made")
        assert await registry.next_part_number("BOUGHT-{seq:04d}") == "BOUGHT-0001"
