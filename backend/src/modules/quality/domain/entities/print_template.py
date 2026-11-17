"""
One row per PrintClassifier (src/modules/quality/domain/value_objects/print_classifier.py).
InitDatabase creates every missing row at startup as an unconfigured slot, and
the application only ever edits them (see GetPrintTemplates, UpdatePrintTemplate
and ResetPrintTemplate), so a template is never created or deleted by a user.

creator_id is nullable because a slot created at startup has no human creator.
It is set once an admin edits the row.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.platform.domain.entities.user import User


@dataclass
class PrintTemplate(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]

    # ── Identity (fixed by the classifier, not user-editable) ─────────
    classifier: PrintClassifier

    # ── Configurable ──────────────────────────────────────────────────
    trigger: PrintTrigger | None  # None = manual only
    source: str | None  # ZPL text, or a JSON block list for dockets
    field_map: dict[str, str] = field(default_factory=dict)
    printer_id: int | None = None
    auto_print: bool = False
    copies_rule: PrintCopiesRule = PrintCopiesRule.FIXED
    copies_fixed: int = 1
    max_copies: int = 50
    design_dpi: int | None = None
    label_width_mm: float | None = None
    label_height_mm: float | None = None
    paper: str | None = None
    enabled: bool = True
    note: str | None = None

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator_full_name: str = ""
    changed_by_id: int | None = None
    changed_by: User | None = None
    printer_name: str = ""

    def as_field_map(self) -> dict[str, Any]:
        return dict(self.field_map)
