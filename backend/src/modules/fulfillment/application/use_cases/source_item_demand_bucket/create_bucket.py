"""
Creates a source-item demand bucket through the shared demand bucket use case.
"""

from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    SourceItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import CreateDemandBucket
from src.modules.fulfillment.application.use_cases.source_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket


class CreateBucket(CreateDemandBucket[SourceItemDemandBucket, SourceItemDemandBucketResult]):
    _spec = SPEC
