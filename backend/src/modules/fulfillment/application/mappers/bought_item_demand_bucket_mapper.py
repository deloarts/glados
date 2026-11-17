"""
Converts between BoughtItemDemandBucket domain entity and DTOs.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    BoughtItemDemandBucketResult,
)
from src.modules.fulfillment.application.mappers.demand_bucket_mapper import demand_bucket_to_result
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket


class BoughtItemDemandBucketMapper:
    @staticmethod
    def to_result(entity: BoughtItemDemandBucket) -> BoughtItemDemandBucketResult:
        return demand_bucket_to_result(BoughtItemDemandBucketResult, entity)
