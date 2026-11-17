"""
Binds the bought-item demand bucket types to the shared demand bucket use cases in
src/modules/fulfillment/application/services/demand_bucket_crud.py.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    BoughtItemDemandBucketResult,
)
from src.modules.fulfillment.application.mappers.bought_item_demand_bucket_mapper import (
    BoughtItemDemandBucketMapper,
)
from src.modules.fulfillment.application.services.demand_bucket_crud import DemandBucketSpec
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket
from src.modules.fulfillment.domain.errors import BoughtItemDemandBucketAlreadyExistsError
from src.modules.fulfillment.domain.errors import BoughtItemDemandBucketNotFoundError

SPEC: DemandBucketSpec[BoughtItemDemandBucket, BoughtItemDemandBucketResult] = DemandBucketSpec(
    entity_cls=BoughtItemDemandBucket,
    to_result=BoughtItemDemandBucketMapper.to_result,
    not_found_error=BoughtItemDemandBucketNotFoundError,
    already_exists_error=BoughtItemDemandBucketAlreadyExistsError,
)
