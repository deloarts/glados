"""
Customer master record: company info, legal/contact details, address, and
VAT identification.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class Customer(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime
    changed: datetime | None
    changes: list[str]
    archived: bool

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    legal_name: str | None
    vat_id: str | None
    level: CustomerLevel

    # ── Address ───────────────────────────────────────────────────────
    street: str | None
    city: str | None
    country: str | None  # ISO 3166-1 alpha-2, e.g. "AT", "DE"
    postal_code: str | None

    # ── Contact ───────────────────────────────────────────────────────
    email: str | None
    phone: str | None
    weblink: str | None

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int

    # ── Denormalized (read-only, populated by repository mapper) ──────
    creator: User | None = None
    changed_by_id: int | None = None
    changed_by: User | None = None

    # Moves on every change of the row, whoever writes it, so an edit form can
    # send the version it read and learn of a concurrent edit
    # (platform/domain/services/edit_version.py).
    edit_version: int = 0
