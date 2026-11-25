"""
CreateLot and the material of a lot's first position: a routing whose first
position goes to a supplier, every step of it with a method that is required
external, starts the lot awaiting its first step with no demand, while the
setting is on. Anything else demands the material, or waits for approval, as
before.
"""

from dataclasses import replace

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_process
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork

_S = SourceApprovalStatus


class _Settings(FakeAdminSettingsRepository):
    def __init__(self, *, enabled: bool = True, approval: bool = False) -> None:
        super().__init__()
        self._enabled = enabled
        self._approval = approval

    async def get_production(self) -> AdminProductionSettings:
        return replace(
            await super().get_production(),
            external_first_step_needs_no_material=self._enabled,
            require_source_item_approval=self._approval,
        )


def _process(id: int, position: int, *, external: bool, group_index: int | None = None):
    process = make_process(id=id, position=position, group_index=group_index)
    process.fabrication_method_required_external = external
    return process


def _inspection(id: int, position: int) -> MadeItemProcess:
    return make_process(
        id=id,
        position=position,
        fabrication_method_id=None,
        role=StepRole.INSPECTION,
        inspection_method_id=1,
    )


async def _create(
    made_item: MadeItem, settings: _Settings
) -> tuple[ProductionLot, FakeSourceItemDemandRepository]:
    lots = FakeProductionLotRepository()
    demands = FakeSourceItemDemandRepository()
    orders = FakeProductionOrderRepository()
    made_demands = FakeMadeItemDemandRepository()
    made_allocations = FakeMadeItemAllocationRepository()
    harness = demand_reconciler_harness(
        lots=lots,
        production_orders=orders,
        made_demands=made_demands,
        made_allocations=made_allocations,
    )
    use_case = CreateLot(
        lot_repo=lots,
        made_item_repo=FakeMadeItemRepository([made_item]),
        demand_repo=made_demands,
        allocation_repo=made_allocations,
        settings_repo=settings,
        source_item_demand_repo=demands,
        order_repo=orders,
        inspection_method_repo=FakeInspectionMethodRepository(),
        machine_repo=FakeProductionMachineRepository(),
        uow=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
        reconciler=harness.reconciler,
    )
    result = await use_case.execute(
        make_user(permissions=[Permission.WRITE_LOTS]),
        CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0),
    )
    lot = await lots.get_by_id(result.id)
    assert lot is not None
    return lot, demands


def _external_first(**sources: int) -> MadeItem:
    return make_made_item(
        processes=[
            _process(1, 0, external=True, group_index=0),
            _process(2, 1, external=True, group_index=0),
            _process(3, 2, external=False, group_index=1),
        ],
        **sources,
    )


class TestCreateLotFirstStepMaterial:
    async def test_external_first_position_awaits_its_first_step_without_a_demand(self):
        lot, demands = await _create(_external_first(source_item_id=3), _Settings())

        assert lot.source_approval_status is _S.AWAITING_FIRST_STEP
        assert lot.input_demand_id is None
        assert demands.demands == {}

    async def test_approval_on_still_awaits_the_first_step_not_approval(self):
        lot, _ = await _create(_external_first(source_item_id=3), _Settings(approval=True))

        assert lot.source_approval_status is _S.AWAITING_FIRST_STEP

    async def test_a_bought_item_source_awaits_the_first_step_too(self):
        lot, _ = await _create(_external_first(bought_item_id=7), _Settings())

        assert lot.source_approval_status is _S.AWAITING_FIRST_STEP
        assert lot.input_demand_id is None

    async def test_setting_off_demands_the_material_as_before(self):
        lot, demands = await _create(_external_first(source_item_id=3), _Settings(enabled=False))

        assert lot.source_approval_status is _S.NOT_REQUIRED
        assert lot.input_demand_id is not None
        assert demands.demands[lot.input_demand_id].quantity == 5.0

    async def test_one_in_house_step_in_the_first_position_demands_the_material(self):
        made_item = make_made_item(
            processes=[
                _process(1, 0, external=True, group_index=0),
                _process(2, 1, external=False, group_index=0),
            ],
            source_item_id=3,
        )

        lot, _ = await _create(made_item, _Settings())

        assert lot.source_approval_status is _S.NOT_REQUIRED
        assert lot.input_demand_id is not None

    async def test_an_external_later_position_does_not_count(self):
        made_item = make_made_item(
            processes=[_process(1, 0, external=False), _process(2, 1, external=True)],
            source_item_id=3,
        )

        lot, _ = await _create(made_item, _Settings(approval=True))

        assert lot.source_approval_status is _S.PENDING

    async def test_an_inspection_first_is_done_in_house(self):
        made_item = make_made_item(
            processes=[_inspection(1, 0), _process(2, 1, external=True)], source_item_id=3
        )

        lot, _ = await _create(made_item, _Settings())

        assert lot.source_approval_status is _S.NOT_REQUIRED
        assert lot.input_demand_id is not None

    async def test_a_lot_without_a_material_source_has_nothing_to_await(self):
        lot, _ = await _create(_external_first(), _Settings())

        assert lot.source_approval_status is _S.NOT_REQUIRED
        assert lot.input_demand_id is None
