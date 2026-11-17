"""
Assigns (or clears, bucket_id=None) a demand item's bucket. Buckets are
shared team display state, not business logic (see
DemandBucketRules), so unlike every other demand item mutation
in this package this never touches `changed`/`changes` and publishes no
domain event. Idempotent: re-assigning the demand's current bucket_id is
a harmless no-op save.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.mappers.bought_item_demand_mapper import (
    BoughtItemDemandItemMapper,
)
from src.modules.fulfillment.domain.errors import BoughtItemDemandBucketNotFoundError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.services.demand_bucket_rules import DemandBucketRules
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    IBoughtItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class SetDemandItemBucket:
    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        bucket_repo: IBoughtItemDemandBucketRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._demands = demand_repo
        self._buckets = bucket_repo
        self._uow = uow

    async def execute(self, actor: User, demand_id: int, bucket_id: int | None) -> DemandItemResult:
        DemandBucketRules.assert_can_write(actor)

        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            DemandItemNotFoundError,
            f"Demand item #{demand_id} not found.",
        )

        if bucket_id is not None and not await self._buckets.get_by_id(bucket_id):
            raise BoughtItemDemandBucketNotFoundError(f"Bucket #{bucket_id} not found.")

        demand.bucket_id = bucket_id
        saved = await self._demands.save(demand)
        await self._uow.commit()
        return BoughtItemDemandItemMapper.to_result(saved)
