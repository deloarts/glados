"""
Catalogue record: what a part IS, manufacturer, order codes, article name.
Project-agnostic. Never belongs to a project or workflow directly.
Status: ACTIVE | INACTIVE | REPLACED
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class BoughtItem(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool

    # ── External core fields ──────────────────────────────────────────
    article_name: str
    order_code_1: str  # primary manufacturer/supplier order code
    order_code_2: str | None  # secondary / alternative code
    gtin: str | None
    ean: str | None
    tariff_number: str | None

    # ── Internal core fields ──────────────────────────────────────────
    status: BoughtItemCatalogueStatus
    data_source: DataSource
    part_number: str | None  # PDM generated part number

    # ── Internal additional fields ────────────────────────────────────
    mass: int | None  # in grams
    note: str | None
    weblink: str | None
    files: list[BoughtItemFile]

    # ── Relations (FK ids only) ───────────────────────────────────────
    creator_id: int
    approver_id: int | None
    manufacturer_id: int
    article_group_ids: list[int]
    successor_item_id: int | None  # points to replacement when REPLACED

    # The manufacturer's product family, Glados-owned on every row.
    product_family_id: int | None = None

    # The EPLAN Data Portal part this item was created from or linked to,
    # and when it was linked or last read from the portal. Written by the
    # Data Portal paths and by PDM ingest, never by the web form. Dual-owned
    # like a made item's source_item_id: pdm_edp_part_id holds the value PDM
    # last sent, and ingest relinks only when that value changes, so a link
    # made in the web survives a sync of an unchanged file.
    edp_part_id: int | None = None
    edp_synced_at: datetime | None = None
    pdm_edp_part_id: int | None = None

    # The item's own delivery tolerances in percent, replacing the ones of
    # the order settings; None takes those. Glados-owned on every row.
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None

    # Latest released PDM revision of the file, `null` on WEB rows.
    # Read-only passthrough: no create/update use case writes this yet,
    # only PDM ingest does.
    revision: str | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    manufacturer_name: str = ""
    article_groups: list[ArticleGroup] = field(default_factory=list)
    product_family: ProductFamily | None = None
    pdf_files: list[BoughtItemFile] = field(default_factory=list)  # PDF-category files only

    # ── PDM link ──────────────────────────────────────────────────────
    vault_id: str | None = None
    pdm_file_id: int | None = None  # PDM document id, row key (vault_id, pdm_file_id)
    pdm_file_version: int | None = None  # version of the latest release ingested
    pdm_synced_at: datetime | None = None
    pdm_sync_state: PdmSyncState | None = None

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
