"""
Binds the source-item demand bucket types to the shared demand bucket use cases in
src/modules/fulfillment/application/services/demand_bucket_crud.py.
"""

from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    SourceItemDemandBucketResult,
)
from src.modules.fulfillment.application.mappers.source_item_demand_bucket_mapper import (
    SourceItemDemandBucketMapper,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import DemandBucketSpec
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket
from src.modules.fulfillment.domain.errors import SourceItemDemandBucketAlreadyExistsError
from src.modules.fulfillment.domain.errors import SourceItemDemandBucketNotFoundError

SPEC: DemandBucketSpec[SourceItemDemandBucket, SourceItemDemandBucketResult] = DemandBucketSpec(
    entity_cls=SourceItemDemandBucket,
    to_result=SourceItemDemandBucketMapper.to_result,
    not_found_error=SourceItemDemandBucketNotFoundError,
    already_exists_error=SourceItemDemandBucketAlreadyExistsError,
)
