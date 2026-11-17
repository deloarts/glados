"""
Reads one made-item demand bucket by id, or a filtered, paginated list of them,
through the shared demand bucket use cases.
"""

from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    MadeItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBuckets
from src.modules.fulfillment.application.use_cases.made_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    MadeItemDemandBucketFilterDto,
)


class GetBucket(GetDemandBucket[MadeItemDemandBucket, MadeItemDemandBucketResult]):
    _spec = SPEC


class GetBuckets(
    GetDemandBuckets[
        MadeItemDemandBucket, MadeItemDemandBucketResult, MadeItemDemandBucketFilterDto
    ]
):
    _spec = SPEC
