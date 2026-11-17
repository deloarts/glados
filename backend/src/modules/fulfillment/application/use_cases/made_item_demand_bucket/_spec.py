"""
Binds the made-item demand bucket types to the shared demand bucket use cases in
src/modules/fulfillment/application/services/demand_bucket_crud.py.
"""

from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    MadeItemDemandBucketResult,
)
from src.modules.fulfillment.application.mappers.made_item_demand_bucket_mapper import (
    MadeItemDemandBucketMapper,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import DemandBucketSpec
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket
from src.modules.fulfillment.domain.errors import MadeItemDemandBucketAlreadyExistsError
from src.modules.fulfillment.domain.errors import MadeItemDemandBucketNotFoundError

SPEC: DemandBucketSpec[MadeItemDemandBucket, MadeItemDemandBucketResult] = DemandBucketSpec(
    entity_cls=MadeItemDemandBucket,
    to_result=MadeItemDemandBucketMapper.to_result,
    not_found_error=MadeItemDemandBucketNotFoundError,
    already_exists_error=MadeItemDemandBucketAlreadyExistsError,
)
