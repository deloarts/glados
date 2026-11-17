"""
A vendor that supplies bought or source items: contact details,
capabilities, and fields for automated procurement.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class Supplier(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    legal_name: str | None
    vat_id: str | None
    level: SupplierLevel
    capability_ids: list[int]
    article_group_ids: list[int]

    # ── Address ───────────────────────────────────────────────────────
    street: str | None
    city: str | None
    country: str | None  # ISO 3166-1 alpha-2, e.g. "AT", "DE"
    postal_code: str | None

    # ── Contact ───────────────────────────────────────────────────────
    email: str | None
    phone: str | None
    weblink: str | None

    # ── Automation ────────────────────────────────────────────────────
    order_email: str | None
    order_language: str | None
    order_template: str | None
    request_email: str | None
    request_language: str | None
    request_template: str | None

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int

    # Calendar days this supplier typically takes to deliver, once ordered.
    # When set, wins outright over the sum of an EXTERNAL/MIXED position's
    # own step lead times for forecasting that position's delivery date
    # (see scheduling.resolve_position_lead_days). None means no
    # supplier-level override, fall back to the steps' own lead times.
    external_lead_time_days: int | None = None
    # The manufacturer code the EPLAN Data Portal uses (SIE, FES), upper case;
    # see domain/services/supplier_edp_code.py.
    edp_code: str | None = None
    # The manufacturer's order code 1 is the portal's type number and its
    # order code 2 the portal's order number, the other way round than for
    # most manufacturers (Festo: DFM-25-50-P-A-GF is order code 1, 170851
    # order code 2).
    edp_type_number_first: bool = False

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None
    capabilities: list[FabricationMethod] = field(default_factory=list)
    article_groups: list[ArticleGroup] = field(default_factory=list)

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
