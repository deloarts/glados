"""
Sets the status of a bought item demand by hand through the status change
the three demand families share (_demand_family/update_status.py). A
`canceled` is handed to CancelDemandItem, so both routes cancel the same way.
A `fulfilled` releases what the demand holds on order lines beyond the pieces
that reached it.
"""

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.unarrived_release import (
    UnarrivedLineRelease,
)
from src.modules.fulfillment.application.use_cases._demand_family.update_status import (
    PermittedDemandCancel,
)
from src.modules.fulfillment.application.use_cases._demand_family.update_status import (
    UpdateDemandStatus,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand._demand_spec import SPEC
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateDemandItemStatus(UpdateDemandStatus[BoughtItemDemandItem, DemandItemResult]):
    _spec = SPEC

    def __init__(
        self,
        demand_repo: IBoughtItemDemandItemRepository,
        cancel_use_case: PermittedDemandCancel[DemandItemResult],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        allocation_repo: IBoughtItemAllocationRepository,
        source_allocation_repo: ISourceItemAllocationRepository,
        order_item_repo: IOrderItemRepository,
    ) -> None:
        super().__init__(
            demand_repo,
            cancel_use_case,
            uow=uow,
            reconciler=reconciler,
            line_release=UnarrivedLineRelease(
                allocation_repo,
                LineFillRepos(bought=allocation_repo, source=source_allocation_repo),
                order_item_repo,
            ),
        )
