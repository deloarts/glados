"""
Converts between SourceItemDemandBucket domain entity and DTOs.
"""

from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    SourceItemDemandBucketResult,
)
from src.modules.fulfillment.application.mappers.demand_bucket_mapper import demand_bucket_to_result
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket


class SourceItemDemandBucketMapper:
    @staticmethod
    def to_result(entity: SourceItemDemandBucket) -> SourceItemDemandBucketResult:
        return demand_bucket_to_result(SourceItemDemandBucketResult, entity)
