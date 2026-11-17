"""
One row per part number ever claimed by a made-item family or a bought
item (docs/FIELD_OWNERSHIP.md principle 2): `part_number` is the natural
key, shared across the whole
application regardless of which catalogue holds it, so `kind` records
which one does. No surrogate id: this is a pure uniqueness ledger, not
an aggregate root, and a made-item revision never adds a second row for
its family (see IPartNumberRegistry.assert_family).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind


@dataclass
class PartNumberRegistryEntry:
    part_number: str
    kind: ItemKind  # MADE or BOUGHT, never SOURCE
    created: datetime


@dataclass(frozen=True)
class UnregisteredPartNumber:
    """A part number a made or bought item carries whose registry row is
    missing or names the other catalogue. `item_id` and `item_public_id` are
    the lowest id among the items carrying it, `kind` is their catalogue and
    `registered_kind` the kind the registry names, None without a row."""

    part_number: str
    kind: ItemKind
    registered_kind: ItemKind | None
    item_id: int
    item_public_id: UUID
