"""
Reads one bought-item demand bucket by id, or a filtered, paginated list of them,
through the shared demand bucket use cases.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    BoughtItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBuckets
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    BoughtItemDemandBucketFilterDto,
)


class GetBucket(GetDemandBucket[BoughtItemDemandBucket, BoughtItemDemandBucketResult]):
    _spec = SPEC


class GetBuckets(
    GetDemandBuckets[
        BoughtItemDemandBucket, BoughtItemDemandBucketResult, BoughtItemDemandBucketFilterDto
    ]
):
    _spec = SPEC
