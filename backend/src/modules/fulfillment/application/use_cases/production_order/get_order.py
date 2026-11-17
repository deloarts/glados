"""Use cases for retrieving production orders with conflict computation against the schedule."""

from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_conflicts_for_orders,
)
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.platform.domain.entities.user import User


class GetProductionOrder:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        pool_repo: IMachinePoolRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._repos = repos
        self._machines = machine_repo
        self._pools = pool_repo

    async def execute(
        self, production_order_id: int, actor: User | None = None
    ) -> ProductionOrderResult:
        """The order with its conflicts, and with an actor its actions."""
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        conflicts = await compute_conflicts_for_orders(
            [order], self._repos, self._machines, pool_repo=self._pools, actor=actor
        )
        return ProductionOrderMapper.to_result(order, conflicts=conflicts[order.id])


class GetProductionOrders:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        pool_repo: IMachinePoolRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._repos = repos
        self._machines = machine_repo
        self._pools = pool_repo

    async def execute(
        self, filters: ProductionOrderFilterDto, actor: User | None = None
    ) -> tuple[int, list[ProductionOrderResult]]:
        """A page of orders with their conflicts, and with an actor their
        actions."""
        total, orders = await self._orders.get_multi(filters)
        conflicts_by_id = await compute_conflicts_for_orders(
            orders, self._repos, self._machines, pool_repo=self._pools, actor=actor
        )
        return total, [
            ProductionOrderMapper.to_result(o, conflicts=conflicts_by_id[o.id]) for o in orders
        ]
