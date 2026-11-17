"""
Domain entity for the made item and revision settings singleton.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.policies.item_field_ownership import RevisionFieldPolicy
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminMadeItemSettings(Entity):
    """Settings for the Made Items domain (fabricated and manufactured items)."""

    item_number_format: str  # e.g. "FAB-{yy}-{seq:05d}"; {seq} must be the last token
    lot_number_format: str  # e.g. "LOT-{yy}-{seq:05d}"; {seq} must be the last token
    part_number_auto: bool  # generate the part number on creation instead of manual entry
    part_number_editable: bool  # whether a user may change the part number after creation

    # ── Revisions ─────────────────────────────────────────────────────
    revision_start: str  # one of revision_scheme.START_REVISIONS, default "0"
    revision_separator: str  # free text, display only, no validation
    revision_skip_ambiguous_letters: bool  # ASME Y14.35 letter skipping
    revision_only_newest_editable: bool  # only the newest revision of a family is editable
    revision_predecessor_status_web: str  # "ask" | a MadeItemCatalogueStatus value
    revision_predecessor_status_pdm: str  # a MadeItemCatalogueStatus value, no "ask"
    revision_field_policy: list[RevisionFieldPolicy]  # one entry per REVISION_POLICY_FIELDS

    # Same meaning as on AdminOrderSettings (orders.py).
    web_creation_allowed: bool
    pdm_part_number_pattern: str

    # ── Document numbers ──────────────────────────────────────────────
    # Calculations and checklists use the revisions above; their document
    # number, shared by every revision of one document, follows these.
    calculation_number_format: str = "CAL-{yy}-{seq:04d}"
    checklist_number_format: str = "CHK-{yy}-{seq:04d}"
    sequence_number_format: str = "SEQ-{yy}-{seq:04d}"
    # Meetings are numbered once each, with no revisions.
    meeting_number_format: str = "MTG-{yy}-{seq:04d}"
