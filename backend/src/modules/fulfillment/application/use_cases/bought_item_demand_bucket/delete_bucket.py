"""
Hard-deletes a bought-item demand bucket through the shared demand bucket use case.
The repository nulls `bucket_id` on every demand it was assigned to in the
same transaction (see SqlAlchemyBoughtItemDemandBucketRepository.delete).
"""

from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    BoughtItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import DeleteDemandBucket
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket


class DeleteBucket(DeleteDemandBucket[BoughtItemDemandBucket, BoughtItemDemandBucketResult]):
    _spec = SPEC
