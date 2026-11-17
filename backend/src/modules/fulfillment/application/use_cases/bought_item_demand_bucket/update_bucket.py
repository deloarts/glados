"""
Updates a bought-item demand bucket's name and color through the shared demand
bucket use case.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    BoughtItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import UpdateDemandBucket
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket


class UpdateBucket(UpdateDemandBucket[BoughtItemDemandBucket, BoughtItemDemandBucketResult]):
    _spec = SPEC
