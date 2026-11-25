"""
ApproveLotSource and SwitchLotMaterialSource and the material of a lot's
first position: a supplier's first position brings the material, so the
switch gives the lot the matching status and no demand, and a MIXED first
position demands only what it makes in house. With the setting off both
demand the material as before.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.use_cases.production_lot.approve_lot_source import (
    ApproveLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_source_item
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemRepository
from tests.unit.production_lot.fakes import fake_line_release
from tests.unit.test_lot_source_approval_use_cases import make_lot

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


def _step(*, external: bool) -> LotStep:
    return LotStep(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        sequence=1,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=1,
        position_id=1,
        source_process_id=None,
        role=StepRole.FABRICATION,
        fabrication_method_required_external=external,
    )


def _first_position(
    kind: LotPositionKind, *, supplier: float = 0.0, external_steps: bool = False
) -> LotPosition:
    position = LotPosition(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=1,
        kind=kind,
        status=LotPositionStatus.PENDING,
        quantity=5.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[_step(external=external_steps)],
    )
    if supplier:
        position.order_item_status = OrderItemStatus.ORDERED
        position.order_item_quantity = supplier
    return position


async def _saved_lot(
    lots: FakeProductionLotRepository, position: LotPosition, **fields: object
) -> ProductionLot:
    lot = await lots.save(make_lot(id=1, quantity=5.0, **fields))  # type: ignore[arg-type]
    steps = position.steps
    await lots.save_position(position)
    for step in steps:
        await lots.save_step(step)
    return lot


class TestApproveFirstStepMaterial:
    def setup_method(self) -> None:
        self.lots = FakeProductionLotRepository()
        self.demands = FakeSourceItemDemandRepository()

    async def _approve(self, settings: _Settings) -> float:
        approve = ApproveLotSource(
            lot_repo=self.lots,
            source_item_demand_repo=self.demands,
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(source_demands=self.demands),
            project_repo=FakeProjectRepository(),
            source_item_repo=FakeSourceItemRepository([make_source_item(id=1)]),
            made_items=FakeMadeItemRepository([make_made_item(id=1)]),  # type: ignore[arg-type]
            settings_repo=settings,
        )
        result = await approve.execute(make_user(permissions=[Permission.MANAGE_LOTS]), 1)
        demand = await self.demands.get_by_id(result.input_demand_id)
        assert demand is not None
        return demand.quantity

    async def test_mixed_first_position_demands_the_in_house_share(self) -> None:
        await _saved_lot(self.lots, _first_position(LotPositionKind.MIXED, supplier=3.0))

        assert await self._approve(_Settings()) == 2.0

    async def test_in_house_first_position_demands_the_whole_lot(self) -> None:
        await _saved_lot(self.lots, _first_position(LotPositionKind.INTERNAL))

        assert await self._approve(_Settings()) == 5.0

    async def test_setting_off_demands_the_whole_lot_for_a_mixed_one(self) -> None:
        await _saved_lot(self.lots, _first_position(LotPositionKind.MIXED, supplier=3.0))

        assert await self._approve(_Settings(enabled=False)) == 5.0


class TestSwitchFirstStepMaterial:
    def setup_method(self) -> None:
        self.lots = FakeProductionLotRepository()
        self.demands = FakeSourceItemDemandRepository()

    async def _switch(self, settings: _Settings) -> ProductionLot:
        allocations = FakeSourceItemAllocationRepository()
        switch = SwitchLotMaterialSource(
            lot_repo=self.lots,
            bought_item_repo=FakeBoughtItemRepository([]),
            source_item_repo=FakeSourceItemRepository(
                [make_source_item(id=1), make_source_item(id=2)]
            ),
            made_item_repo=FakeMadeItemRepository([]),
            source_item_demand_repo=self.demands,
            source_item_allocation_repo=allocations,
            settings_repo=settings,
            project_repo=FakeProjectRepository(),
            line_release=fake_line_release(allocations),
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(source_demands=self.demands),
        )
        await switch.execute(
            make_user(permissions=[Permission.WRITE_LOTS]),
            1,
            SwitchLotMaterialSourceCommand(source_item_id=2, confirm_replace_demand=True),
        )
        lot = await self.lots.get_by_id(1)
        assert lot is not None
        return lot

    async def test_external_first_position_is_supplier_sourced_without_a_demand(self) -> None:
        await _saved_lot(
            self.lots,
            _first_position(LotPositionKind.EXTERNAL, supplier=5.0),
            source_approval_status=_S.SUPPLIER_SOURCED,
        )

        lot = await self._switch(_Settings(approval=True))

        assert lot.source_approval_status is _S.SUPPLIER_SOURCED
        assert lot.input_demand_id is None

    async def test_predicted_external_first_position_awaits_it(self) -> None:
        await _saved_lot(
            self.lots,
            _first_position(LotPositionKind.UNASSIGNED, external_steps=True),
            source_approval_status=_S.AWAITING_FIRST_STEP,
        )

        lot = await self._switch(_Settings())

        assert lot.source_approval_status is _S.AWAITING_FIRST_STEP
        assert lot.input_demand_id is None

    async def test_setting_off_demands_the_new_source(self) -> None:
        await _saved_lot(
            self.lots,
            _first_position(LotPositionKind.EXTERNAL, supplier=5.0),
            source_approval_status=_S.NOT_REQUIRED,
        )

        lot = await self._switch(_Settings(enabled=False))

        assert lot.source_approval_status is _S.NOT_REQUIRED
        assert lot.input_demand_id is not None

    async def test_mixed_first_position_demands_the_in_house_share(self) -> None:
        await _saved_lot(
            self.lots,
            _first_position(LotPositionKind.MIXED, supplier=3.0),
            source_approval_status=_S.NOT_REQUIRED,
        )

        lot = await self._switch(_Settings())

        demand = await self.demands.get_by_id(lot.input_demand_id)  # type: ignore[arg-type]
        assert demand is not None and demand.quantity == 2.0
