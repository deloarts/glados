"""
MadeItem is the catalogue entry for a manufactured part: identified by
(part_number, revision), never edited in place, a new revision copies the
row instead. Carries the PDM-owned fields (revision, material, routing)
alongside web-owned fields, with data_source recording which side owns it.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MadeItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool

    # ── External core fields ──────────────────────────────────────────
    revision: str  # PDM revision string
    revision_date: date | None  # PDM revision date
    revision_note: str | None  # PDM revision note

    article_name: str

    # ── Internal core fields ──────────────────────────────────────────
    status: MadeItemCatalogueStatus
    data_source: DataSource
    part_number: str | None  # free-text part number (auto-numbering via PDM is a later concern)

    # ── Internal additional fields ────────────────────────────────────
    material: str | None  # ISO material number, e.g. "1.0037"
    mass: int | None  # in grams
    base_size: str | None
    note: str | None
    weblink: str | None
    files: list[MadeItemFile]

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    approver_id: int | None
    bought_item_id: int | None  # BoughtItem (optional input: buy this exact catalogue part)
    source_item_id: int | None  # SourceItem (optional input: raw stock spec), mutually exclusive
    # with bought_item_id
    article_group_ids: list[int]
    successor_item_id: int | None  # points to replacement when REPLACED
    changed_by_id: int | None  # user behind the most recent update

    # ── Customer data ─────────────────────────────────────────────────
    # A customer item is a made item with a customer: the part was received
    # from that customer, usually as a model, and keeps the customer's own
    # identity for it. The customer part number is no key, since two
    # customers may use the same number.
    customer_id: int | None = None
    customer_part_number: str | None = None
    customer_revision: str | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    customer_name: str | None = None
    creator: User | None = None
    changed_by: User | None = None
    bought_item: BoughtItem | None = None
    source_item: SourceItem | None = None
    article_groups: list[ArticleGroup] = field(default_factory=list)
    processes: list[MadeItemProcess] = field(default_factory=list)
    source_label: str = ""
    source_sublabel: str = ""

    # ── PDM link ──────────────────────────────────────────────────────
    vault_id: str | None = None
    pdm_file_id: int | None = None  # PDM document id, same value on every revision row
    pdm_file_version: int | None = None  # check-in version released as this revision
    pdm_synced_at: datetime | None = None
    pdm_sync_state: PdmSyncState | None = None
    # Shadow of source_item_id: the value last received from PDM. A web
    # edit survives every sync where the CAD value is unchanged; ingest
    # applies the PDM value only when it itself changed. See
    # docs/reference/field-ownership.md section 1.7.
    pdm_source_item_id: int | None = None

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
