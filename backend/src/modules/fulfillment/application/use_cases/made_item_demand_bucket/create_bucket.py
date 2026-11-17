"""
Creates a made-item demand bucket through the shared demand bucket use case.
"""

from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    MadeItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import CreateDemandBucket
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket


class CreateBucket(CreateDemandBucket[MadeItemDemandBucket, MadeItemDemandBucketResult]):
    _spec = SPEC
