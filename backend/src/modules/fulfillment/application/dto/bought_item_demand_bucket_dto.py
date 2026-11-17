"""
Input commands and output results for bought-item demand bucket use
cases. These cross the application boundary, not the same as API schemas.
"""

from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketCommandBase
from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketResultBase

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateBoughtItemDemandBucketCommand(DemandBucketCommandBase):
    pass


class UpdateBoughtItemDemandBucketCommand(DemandBucketCommandBase):
    pass


# ── Results (outbound) ────────────────────────────────────────────────


class BoughtItemDemandBucketResult(DemandBucketResultBase):
    pass
