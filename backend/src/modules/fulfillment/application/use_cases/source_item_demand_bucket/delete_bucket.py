"""
Hard-deletes a source-item demand bucket through the shared demand bucket use case.
The repository nulls `bucket_id` on every demand it was assigned to in the
same transaction (see SqlAlchemySourceItemDemandBucketRepository.delete).
"""

from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    SourceItemDemandBucketResult,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import DeleteDemandBucket
from src.modules.fulfillment.application.use_cases.source_item_demand_bucket._spec import SPEC
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket


class DeleteBucket(DeleteDemandBucket[SourceItemDemandBucket, SourceItemDemandBucketResult]):
    _spec = SPEC
