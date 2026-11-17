"""
Application-wide part-number uniqueness ledger (docs/FIELD_OWNERSHIP.md
principle 2). It holds one row per number claimed by a made-item family or a
bought item, so the two catalogues never collide even when they share a
numbering format. Writes run in the claiming item's transaction and never
commit.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.entities.part_number_registry import UnregisteredPartNumber


@runtime_checkable
class IPartNumberRegistry(Protocol):
    async def owner_of(self, part_number: str) -> PartNumberRegistryEntry | None:
        """The registry row for `part_number`, without claiming anything, so it is
        safe outside a write transaction. ValidatePdmPayload's dry run uses it to
        report a number held by the other catalogue."""
        ...

    async def claim(self, part_number: str, kind: str) -> None:
        """Inserts the registry row for `part_number` and `kind`. Raises
        PartNumberInUseError naming the owning kind when the number is already
        registered, to any kind; the table's primary key is the hard guarantee
        against a concurrent claim."""
        ...

    async def assert_family(self, part_number: str, kind: str) -> None:
        """Makes sure `part_number` is registered to `kind`, for made-item revision
        creation, where only the family registers its number. A matching entry is
        a no-op, a missing one is claimed, and one under another kind raises
        PartNumberInUseError."""
        ...

    async def release_if_unused(self, part_number: str) -> None:
        """Deletes the registry row for `part_number` unless a made or bought item
        row still carries it, archived rows and every revision included. Every
        path that frees a number calls it, such as a merge that deletes its
        source or a renumber that moved every row off the old number."""
        ...

    async def all_entries(self) -> list[PartNumberRegistryEntry]:
        """Every registry row, unpaged, which is fine at vault scale. Read-only;
        ReconcilePdmVault uses it to find orphaned claims that no live item
        carries."""
        ...

    async def find_unregistered_holders(self) -> list[UnregisteredPartNumber]:
        """Every part number a made or bought item carries, archived rows and
        every revision included, whose registry row is missing or names the
        other catalogue, one per number and catalogue, ordered by number.
        Read-only; the lifecycle drift report lists them."""
        ...

    async def next_part_number(self, template: str) -> str:
        """The next number for `template` (see numbering_format.render_prefix),
        scanned over this table rather than either item table, so made and bought
        items sharing a format draw from one sequence."""
        ...
