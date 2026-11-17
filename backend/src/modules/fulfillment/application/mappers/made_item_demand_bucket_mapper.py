"""
Converts between MadeItemDemandBucket domain entity and DTOs.
"""

from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    MadeItemDemandBucketResult,
)
from src.modules.fulfillment.application.mappers.demand_bucket_mapper import demand_bucket_to_result
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket


class MadeItemDemandBucketMapper:
    @staticmethod
    def to_result(entity: MadeItemDemandBucket) -> MadeItemDemandBucketResult:
        return demand_bucket_to_result(MadeItemDemandBucketResult, entity)
