"""
Sets the status of a source item demand by hand through the status change
the three demand families share (_demand_family/update_status.py). A
`canceled` is handed to CancelSourceItemDemand.execute_permitted together
with the caller's choice for the lot the demand feeds, so both routes cancel
the same way, while who may do it is decided by
assert_can_change_demand_status, not by the lot permissions of the cancel
route. A `fulfilled` releases what the demand holds on order lines beyond
the pieces that reached it.
"""

from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.unarrived_release import (
    UnarrivedLineRelease,
)
from src.modules.fulfillment.application.use_cases._demand_family.update_status import (
    UpdateDemandStatus,
)
from src.modules.fulfillment.application.use_cases.source_item_demand._spec import SPEC
from src.modules.fulfillment.application.use_cases.source_item_demand.cancel_source_item_demand import (
    CancelSourceItemDemand,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateSourceItemDemandStatus(
    UpdateDemandStatus[SourceItemDemandItem, SourceItemDemandResult]
):
    _spec = SPEC

    def __init__(
        self,
        demand_repo: ISourceItemDemandRepository,
        cancel_use_case: CancelSourceItemDemand,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        allocation_repo: ISourceItemAllocationRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
    ) -> None:
        super().__init__(
            demand_repo,
            cancel_use_case,
            uow=uow,
            reconciler=reconciler,
            line_release=UnarrivedLineRelease(
                allocation_repo,
                LineFillRepos(bought=bought_allocation_repo, source=allocation_repo),
                order_item_repo,
            ),
        )
        self._source_cancel = cancel_use_case

    async def _hand_over_cancel(
        self, actor: User, demand_id: int, cancel_lot: bool | None
    ) -> SourceItemDemandResult:
        return await self._source_cancel.execute_permitted(actor, demand_id, cancel_lot=cancel_lot)
