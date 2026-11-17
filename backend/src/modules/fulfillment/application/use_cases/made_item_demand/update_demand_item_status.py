"""
Sets the status of a made item demand by hand through the status change the
three demand families share (_demand_family/update_status.py). A `canceled`
is never a plain write: it is handed to CancelMadeItemDemand, because a
canceled demand takes its lots, and their production orders, supplier order
items and raw-material demands, down with it. The hand-over lives in the use
case rather than in the endpoint so that no caller can reach CANCELED while
skipping the cascade. A `fulfilled` leaves the demand's lot allocations as
they are.
"""

from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases._demand_family.update_status import (
    PermittedDemandCancel,
)
from src.modules.fulfillment.application.use_cases._demand_family.update_status import (
    UpdateDemandStatus,
)
from src.modules.fulfillment.application.use_cases.made_item_demand._spec import SPEC
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateDemandItemStatus(UpdateDemandStatus[MadeItemDemandItem, MadeItemDemandItemResult]):
    _spec = SPEC

    def __init__(
        self,
        demand_repo: IMadeItemDemandItemRepository,
        cancel_use_case: PermittedDemandCancel[MadeItemDemandItemResult],
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(
            demand_repo, cancel_use_case, uow=uow, reconciler=reconciler, line_release=None
        )
