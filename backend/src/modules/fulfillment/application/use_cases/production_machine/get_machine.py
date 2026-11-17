"""Use cases for retrieving production machine data and paginated machine lists."""

from src.modules.catalogue.domain.errors import ProductionMachineNotFoundError
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.application.mappers.machine_downtime_mapper import (
    MachineDowntimeMapper,
)
from src.modules.fulfillment.application.mappers.production_machine_mapper import (
    ProductionMachineMapper,
)
from src.modules.fulfillment.domain.services.production_machine_status_rules import (
    resolve_machine_status,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    IMachineDowntimeRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.shared_kernel.domain.services.clock import now_utc


class PaginatedProductionMachines:
    def __init__(self, total: int, items: list[ProductionMachineResult]):
        self.total = total
        self.items = items


class GetProductionMachine:
    def __init__(
        self,
        machine_repo: IProductionMachineRepository,
        downtime_repo: IMachineDowntimeRepository | None = None,
        order_repo: IProductionOrderRepository | None = None,
    ) -> None:
        self._machines = machine_repo
        self._downtimes = downtime_repo
        self._orders = order_repo

    async def execute(self, machine_id: int) -> ProductionMachineResult:
        machine = found_or_raise(
            await self._machines.get_by_id(machine_id),
            ProductionMachineNotFoundError,
            f"Production machine #{machine_id} not found.",
        )
        open_downtime = None
        if self._downtimes is not None:
            open_downtime = (
                await self._downtimes.get_open_by_machine_ids([machine_id], started_by=now_utc())
            ).get(machine_id)
        active_orders = (
            (await self._orders.get_active_by_machine_ids([machine_id])).get(machine_id, [])
            if self._orders is not None
            else []
        )
        live_order_count = (
            (await self._orders.count_live_by_machine_ids([machine_id])).get(machine_id, 0)
            if self._orders is not None
            else 0
        )
        status = resolve_machine_status(
            active_orders=active_orders, has_open_downtime=open_downtime is not None
        )
        return ProductionMachineMapper.to_result(
            machine,
            open_downtime=MachineDowntimeMapper.to_open_result(open_downtime)
            if open_downtime
            else None,
            status=status,
            active_orders=active_orders,
            live_order_count=live_order_count,
        )


class GetProductionMachines:
    def __init__(
        self,
        machine_repo: IProductionMachineRepository,
        downtime_repo: IMachineDowntimeRepository | None = None,
        order_repo: IProductionOrderRepository | None = None,
    ) -> None:
        self._machines = machine_repo
        self._downtimes = downtime_repo
        self._orders = order_repo

    async def execute(self, filters: ProductionMachineFilterDto) -> PaginatedProductionMachines:
        total, items = await self._machines.get_multi(filters)
        # One batched query per collaborator for every machine on the
        # page, rather than one lookup per row. Skipped entirely when a
        # collaborator wasn't wired in (see GetProductionMachine).
        open_by_machine = (
            await self._downtimes.get_open_by_machine_ids(
                [m.id for m in items], started_by=now_utc()
            )
            if self._downtimes is not None
            else {}
        )
        active_by_machine = (
            await self._orders.get_active_by_machine_ids([m.id for m in items])
            if self._orders is not None
            else {}
        )
        live_by_machine = (
            await self._orders.count_live_by_machine_ids([m.id for m in items])
            if self._orders is not None
            else {}
        )
        return PaginatedProductionMachines(
            total=total,
            items=[
                ProductionMachineMapper.to_result(
                    m,
                    open_downtime=MachineDowntimeMapper.to_open_result(open_by_machine[m.id])
                    if m.id in open_by_machine
                    else None,
                    status=resolve_machine_status(
                        active_orders=active_by_machine.get(m.id, []),
                        has_open_downtime=m.id in open_by_machine,
                    ),
                    active_orders=active_by_machine.get(m.id, []),
                    live_order_count=live_by_machine.get(m.id, 0),
                )
                for m in items
            ],
        )
