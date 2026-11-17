"""
What other modules and the read tier read of Planning & fulfillment: narrow query
protocols over its repositories, which the repositories satisfy as they are, and the filters
they take. Writes go through Planning & fulfillment' use cases.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)

__all__ = [
    "IMachineDowntimeQueries",
    "IMachinePoolQueries",
    "IOrderItemDeliveryQueries",
    "IOrderItemQueries",
    "IOrderQueries",
    "IProductionLotQueries",
    "IProductionMachineQueries",
    "IProductionOrderInterruptionQueries",
    "IProductionOrderQueries",
    "LotFilterDto",
    "OrderFilterDto",
    "ProductionOrderFilterDto",
]


@runtime_checkable
class IMachineDowntimeQueries(Protocol):
    async def minutes_by_machine_in_period(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> dict[int, int]:
        """Downtime minutes per machine overlapping [start, end), for the
        availability KPI. An open downtime counts up to `end` (or `now`,
        whichever is earlier) as if it were still ongoing throughout the
        period. Machines with no overlapping downtime are absent from the
        result."""
        ...

    async def get_open_by_machine_ids(
        self, machine_ids: list[int], *, started_by: datetime | None = None
    ) -> dict[int, MachineDowntime]:
        """The open downtime of each machine that has one, in one query.
        With started_by, only downtimes that started by then count."""
        ...


@runtime_checkable
class IMachinePoolQueries(Protocol):
    async def get_by_id(self, id: int) -> MachinePool | None:
        """Regardless of `archived`, references must resolve."""
        ...


@runtime_checkable
class IOrderQueries(Protocol):
    async def get_by_id(self, id: int) -> Order | None: ...

    async def get_multi(self, filters: OrderFilterDto) -> tuple[int, list[Order]]: ...


@runtime_checkable
class IOrderItemQueries(Protocol):
    async def get_by_id(self, id: int) -> OrderItem | None: ...

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]: ...

    async def get_by_order_ids(self, order_ids: list[int]) -> list[OrderItem]: ...


@runtime_checkable
class IOrderItemDeliveryQueries(Protocol):
    async def get_by_id(self, id: int) -> OrderItemDelivery | None: ...


@runtime_checkable
class IProductionLotQueries(Protocol):
    async def get_by_id(self, id: int) -> ProductionLot | None: ...

    async def get_by_public_id(self, public_id: UUID) -> ProductionLot | None: ...

    async def get_by_ids(self, ids: list[int]) -> list[ProductionLot]:
        """The lots with their positions."""
        ...

    async def get_position_by_id(self, position_id: int) -> LotPosition | None: ...


@runtime_checkable
class IProductionMachineQueries(Protocol):
    async def get_all(self) -> list[ProductionMachine]:
        """Unpaginated: every non-archived machine, no skip/limit/
        total. Scheduling hot paths (auto-plan, schedule board) need the
        *entire* active roster to consider every machine, not a UI page
        of it; `get_multi(FilterDto())` silently clamps to
        `DEFAULT_PAGE_SIZE` (pagination.py) past the 100th machine.
        `get_multi` stays exactly as-is for genuinely paginated callers
        (production_machine/get_machine.py)."""
        ...


@runtime_checkable
class IProductionOrderInterruptionQueries(Protocol):
    async def get_by_order_ids(self, order_ids: list[int]) -> list[ProductionOrderInterruption]:
        """Every interruption (open or closed) for the given orders,
        oldest first, batched for the order-list/detail read path."""
        ...


@runtime_checkable
class IProductionOrderQueries(Protocol):
    async def get_by_id(self, id: int) -> ProductionOrder | None: ...

    async def get_completion_by_id(
        self, completion_id: int
    ) -> ProductionOrderCompletion | None: ...
