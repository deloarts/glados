"""
Catalogue record for a made item's raw material input. A pure standalone
raw-material spec (type/dimension/material/mass/manufacturer/note), it no
longer wraps a BoughtItem or MadeItem; MadeItem/ProductionLot point at
whichever catalogue entry they mean directly instead.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class SourceItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool

    # ── Core fields ─────────────────────────────────────────────────────
    type_id: int
    dimension: str | None
    material: str
    mass: int | None  # in grams
    note: str | None
    order_code_1: str | None  # primary supplier order code
    order_code_2: str | None  # secondary / alternative supplier order code

    # ── Internal core fields ──────────────────────────────────────────
    status: SourceItemCatalogueStatus

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    approver_id: int | None
    manufacturer_id: int | None
    successor_item_id: int | None  # points to replacement when REPLACED

    # The item's own delivery tolerances in percent, replacing the ones of
    # the order settings; None takes those.
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    manufacturer_name: str = ""
    type_name: LocalizedText = field(default_factory=LocalizedText)

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
