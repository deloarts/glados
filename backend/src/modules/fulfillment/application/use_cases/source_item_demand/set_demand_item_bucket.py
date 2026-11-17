"""
Assigns (or clears, bucket_id=None) a demand item's bucket. Buckets are
shared team display state, not business logic (see
DemandBucketRules), so unlike every other demand item mutation
in this package this never touches `changed`/`changes` and publishes no
domain event. Idempotent: re-assigning the demand's current bucket_id is
a harmless no-op save.
"""

from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.domain.errors import SourceItemDemandBucketNotFoundError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.services.demand_bucket_rules import DemandBucketRules
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    ISourceItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class SetDemandItemBucket:
    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        bucket_repo: ISourceItemDemandBucketRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._demands = demand_repo
        self._buckets = bucket_repo
        self._uow = uow

    async def execute(
        self, actor: User, demand_id: int, bucket_id: int | None
    ) -> SourceItemDemandResult:
        DemandBucketRules.assert_can_write(actor)

        demand = found_or_raise(
            await self._demands.get_by_id(demand_id),
            SourceItemDemandNotFoundError,
            f"Source item demand #{demand_id} not found.",
        )

        if bucket_id is not None and not await self._buckets.get_by_id(bucket_id):
            raise SourceItemDemandBucketNotFoundError(f"Bucket #{bucket_id} not found.")

        demand.bucket_id = bucket_id
        saved = await self._demands.save(demand)
        await self._uow.commit()
        return SourceItemDemandMapper.to_result(saved)
