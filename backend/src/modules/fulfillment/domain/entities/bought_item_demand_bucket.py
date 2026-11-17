"""
A bucket is shared team display state for triaging bought-item demands
(see DemandBucketRules): it must never influence business
logic (allocation, ordering, status), only filtering/sorting/grouping
may read it. A demand is in one or no bucket.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class BoughtItemDemandBucket(Entity):
    # ── Server-managed ────────────────────────────────────────────────
    created: datetime

    # ── Core fields ───────────────────────────────────────────────────
    name: str
    color: str

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: int
