"""
Reads one source-item demand bucket by id, or a filtered, paginated list of them,
through the shared demand bucket use cases.
"""

from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    SourceItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBucket
from src.modules.fulfillment.application.services.demand_bucket_crud import GetDemandBuckets
from src.modules.fulfillment.application.use_cases.source_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    SourceItemDemandBucketFilterDto,
)


class GetBucket(GetDemandBucket[SourceItemDemandBucket, SourceItemDemandBucketResult]):
    _spec = SPEC


class GetBuckets(
    GetDemandBuckets[
        SourceItemDemandBucket, SourceItemDemandBucketResult, SourceItemDemandBucketFilterDto
    ]
):
    _spec = SPEC
