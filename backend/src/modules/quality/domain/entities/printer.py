"""
A configured network printer used for ZPL label printing or IPP docket
printing, holding its connection details and per-device quirks such as
the IPP URI path.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.catalogue.domain.entities.bought_item import BoughtItem
    from src.modules.platform.domain.entities.user import User


@dataclass
class Printer(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    internal_name: str | None
    kind: PrinterKind

    # ── Connection ────────────────────────────────────────────────────
    host: str
    port: int
    timeout_seconds: float
    transport: str  # PrinterTransport
    # IPP only. The bizhub answers "client-error-not-found" on the usual
    # "/ipp/print" path and only accepts the bare root, verified with the
    # prototype's Get-Printer-Attributes probe. Kept per-printer, not a
    # constant, since another IPP device may need the conventional path.
    ipp_uri_path: str

    # ── ZPL specifics ────────────────────────────────────────────────
    # The printer's own FORMAT CONVERT setting (front-panel only, no SGD on
    # this firmware) doubles every coordinate in an incoming format when set
    # to 150->300. Proven by sending ^PW413 and reading ezpl.print_width
    # back as 826. Templates are authored at head_dpi / format_convert_factor
    # and this is the single place to correct a mismatch if the front-panel
    # setting ever changes.
    head_dpi: int | None
    format_convert_factor: int | None

    # ── IPP specifics ────────────────────────────────────────────────
    default_media: str | None

    # ── Descriptive ───────────────────────────────────────────────────
    location: str | None
    vendor: str | None
    model: str | None
    firmware: str | None

    # FK-id view of the m:n printer_bought_item table, consumables (labels,
    # ribbon, toner) this printer uses, for quick reordering.
    bought_item_ids: list[int]

    enabled: bool
    is_default: bool
    note: str | None

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
    creator_full_name: str = ""
    changed_by_id: int | None = None
    changed_by: User | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    bought_items: list[BoughtItem] = field(default_factory=list)
