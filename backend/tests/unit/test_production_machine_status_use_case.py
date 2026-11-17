"""
Unit tests for the status/active_orders wiring in GetProductionMachine and
GetProductionMachines: the batched IProductionOrderRepository.
get_active_by_machine_ids lookup, combined with the open-downtime lookup
already covered by test_machine_downtime_use_cases.py, resolved through
resolve_machine_status. No database, no HTTP, all dependencies replaced
with in-memory fakes.
"""

from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachines,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from tests.unit.auto_plan._helpers import make_order
from tests.unit.test_machine_downtime_use_cases import FakeMachineDowntimeRepository
from tests.unit.test_machine_downtime_use_cases import make_downtime
from tests.unit.test_production_machine_use_cases import FakeProductionMachineRepository
from tests.unit.test_production_machine_use_cases import make_machine


class FakeProductionOrderRepositoryForStatus:
    """Minimal fake, only the batched methods this wiring calls."""

    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self._orders = orders or []

    async def get_active_by_machine_ids(
        self, machine_ids: list[int]
    ) -> dict[int, list[ProductionOrder]]:
        grouped: dict[int, list[ProductionOrder]] = {}
        for order in self._orders:
            if order.machine_id in machine_ids:
                grouped.setdefault(order.machine_id, []).append(order)
        return grouped

    async def count_live_by_machine_ids(self, machine_ids: list[int]) -> dict[int, int]:
        counts: dict[int, int] = {}
        for order in self._orders:
            if order.machine_id in machine_ids:
                counts[order.machine_id] = counts.get(order.machine_id, 0) + 1
        return counts


class TestGetProductionMachineStatus:
    async def test_no_collaborators_defaults_to_idle(self):
        """Mirrors the constructor's original single-arg call shape; the
        collaborator is optional, so status still resolves rather than
        raising."""
        machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        use_case = GetProductionMachine(machine_repo)
        result = await use_case.execute(machine_id=1)
        assert result.status == "idle"
        assert result.active_orders == []

    async def test_in_progress_order_reports_running_with_active_orders(self):
        machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        order_repo = FakeProductionOrderRepositoryForStatus(
            [make_order(id=10, lot_id=1, machine_id=1, status=ProductionOrderStatus.IN_PROGRESS)]
        )
        use_case = GetProductionMachine(machine_repo, order_repo=order_repo)
        result = await use_case.execute(machine_id=1)
        assert result.status == "running"
        assert [o.id for o in result.active_orders] == [10]
        assert result.active_orders[0].production_order_number == "PO-0010"
        assert result.active_orders[0].status == "in_progress"

    async def test_open_downtime_wins_over_a_running_order(self):
        machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        order_repo = FakeProductionOrderRepositoryForStatus(
            [make_order(id=10, lot_id=1, machine_id=1, status=ProductionOrderStatus.IN_PROGRESS)]
        )
        downtime_repo = FakeMachineDowntimeRepository([make_downtime(id=1, machine_id=1)])
        use_case = GetProductionMachine(
            machine_repo, downtime_repo=downtime_repo, order_repo=order_repo
        )
        result = await use_case.execute(machine_id=1)
        assert result.status == "down"

    async def test_machine_with_no_active_orders_is_idle(self):
        machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        order_repo = FakeProductionOrderRepositoryForStatus([])
        use_case = GetProductionMachine(machine_repo, order_repo=order_repo)
        result = await use_case.execute(machine_id=1)
        assert result.status == "idle"


class TestGetProductionMachinesStatus:
    async def test_batched_lookup_resolves_status_per_machine(self):
        """One get_active_by_machine_ids call covers every machine on the
        page, each resolving its own status independently."""
        machine_repo = FakeProductionMachineRepository(
            [
                make_machine(id=1, internal_name="Running Mill"),
                make_machine(id=2, internal_name="Paused Mill"),
                make_machine(id=3, internal_name="Idle Mill"),
            ]
        )
        order_repo = FakeProductionOrderRepositoryForStatus(
            [
                make_order(id=10, lot_id=1, machine_id=1, status=ProductionOrderStatus.IN_PROGRESS),
                make_order(id=11, lot_id=1, machine_id=2, status=ProductionOrderStatus.PAUSED),
            ]
        )
        use_case = GetProductionMachines(machine_repo, order_repo=order_repo)
        result = await use_case.execute(ProductionMachineFilterDto())
        by_name = {m.internal_name: m for m in result.items}
        assert by_name["Running Mill"].status == "running"
        assert by_name["Paused Mill"].status == "paused"
        assert by_name["Idle Mill"].status == "idle"
        assert by_name["Idle Mill"].active_orders == []

    async def test_no_order_repo_defaults_every_machine_to_idle(self):
        machine_repo = FakeProductionMachineRepository([make_machine(id=1)])
        use_case = GetProductionMachines(machine_repo)
        result = await use_case.execute(ProductionMachineFilterDto())
        assert result.items[0].status == "idle"
