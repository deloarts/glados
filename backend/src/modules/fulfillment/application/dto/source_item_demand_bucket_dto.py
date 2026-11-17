"""
Input commands and output results for source-item demand bucket use
cases. These cross the application boundary, not the same as API schemas.
"""

from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketCommandBase
from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketResultBase

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateSourceItemDemandBucketCommand(DemandBucketCommandBase):
    pass


class UpdateSourceItemDemandBucketCommand(DemandBucketCommandBase):
    pass


# ── Results (outbound) ────────────────────────────────────────────────


class SourceItemDemandBucketResult(DemandBucketResultBase):
    pass
