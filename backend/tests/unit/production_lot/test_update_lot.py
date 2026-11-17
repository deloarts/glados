"""
Unit tests for TestUpdateLot, TestSwitchLotMaterialSource. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.update_lot import UpdateLot
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotHasOpenDemandError
from src.modules.fulfillment.domain.errors import LotHasPlacedDemandError
from src.modules.fulfillment.domain.errors import LotRawMaterialAlreadyLinkedError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot._helpers import make_bought_item
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_source_item
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import fake_line_release
from tests.unit.production_lot.fakes import lot_reconciler


class TestUpdateLot:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        lot = ProductionLot(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            required_delivery_date=date(2026, 3, 1),
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        self.lot = await self.lot_repo.save(lot)
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])
        self.use_case = UpdateLot(
            lot_repo=self.lot_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )

    async def test_sets_required_delivery_date(self):
        result = await self.use_case.execute(
            self.actor,
            self.lot.id,
            UpdateLotCommand(required_delivery_date=date(2026, 7, 1)),
        )
        assert result.required_delivery_date == date(2026, 7, 1)

    async def test_clears_required_delivery_date_when_explicitly_provided_as_none(self):
        # Unlike note/priority (never clearable via this command),
        # required_delivery_date must support reverting to the
        # demand-derived target: the command explicitly includes the
        # field (even though its value is None), which model_fields_set
        # distinguishes from simply omitting it.
        result = await self.use_case.execute(
            self.actor,
            self.lot.id,
            UpdateLotCommand(required_delivery_date=None),
        )
        assert result.required_delivery_date is None

    async def test_leaves_required_delivery_date_untouched_when_omitted(self):
        result = await self.use_case.execute(
            self.actor,
            self.lot.id,
            UpdateLotCommand(note="unrelated update"),
        )
        assert result.required_delivery_date == date(2026, 3, 1)

    async def test_records_a_field_diff_in_the_changelog_and_event_when_something_changes(self):
        await self.use_case.execute(
            self.actor,
            self.lot.id,
            UpdateLotCommand(note="urgent rework", priority="high"),
        )
        expected = "Lot updated:\n  • note: None → 'urgent rework'\n  • priority: 'normal' → 'high'"

        updated = await self.lot_repo.get_by_id(self.lot.id)
        assert updated is not None
        assert updated.changes[-1].endswith(expected)

        events = await self.lot_repo.get_events(self.lot.id)
        assert events[-1].summary == expected

    async def test_logs_no_changes_when_nothing_actually_changed(self):
        await self.use_case.execute(self.actor, self.lot.id, UpdateLotCommand())

        updated = await self.lot_repo.get_by_id(self.lot.id)
        assert updated is not None
        assert updated.changes[-1].endswith("No changes.")

        events = await self.lot_repo.get_events(self.lot.id)
        assert events[-1].summary == "No changes."


class TestSwitchLotMaterialSource:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.bought_item_repo = FakeBoughtItemRepository([make_bought_item(id=1)])
        self.source_item_repo = FakeSourceItemRepository([make_source_item(id=1)])
        self.made_item_repo = FakeMadeItemRepository([make_made_item(id=1)])
        self.demand_repo = FakeSourceItemDemandRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _use_case(self, recompute_schedule=None) -> SwitchLotMaterialSource:
        return SwitchLotMaterialSource(
            lot_repo=self.lot_repo,
            bought_item_repo=self.bought_item_repo,
            source_item_repo=self.source_item_repo,
            made_item_repo=self.made_item_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=(allocations := FakeSourceItemAllocationRepository()),
            settings_repo=FakeAdminSettingsRepository(),
            project_repo=FakeProjectRepository(),
            line_release=fake_line_release(allocations),
            recompute_schedule=recompute_schedule,
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
        )

    async def _make_lot(self, **overrides) -> ProductionLot:
        defaults = dict(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        defaults.update(overrides)
        return await self.lot_repo.save(ProductionLot(**defaults))

    async def test_no_existing_demand_creates_one_for_new_bought_source(self):
        lot = await self._make_lot()
        use_case = self._use_case()
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
        )
        assert result.source_bought_item_id == 1
        assert result.input_demand_id is not None
        demand = await self.demand_repo.get_by_id(result.input_demand_id)
        assert demand.bought_item_id == 1
        assert demand.canceled_at is None

    @pytest.mark.parametrize(
        "status", [LotStatus.COMPLETED, LotStatus.CANCELED, LotStatus.SCRAPPED]
    )
    async def test_an_ended_lot_keeps_its_source_also_for_a_manager(self, status):
        lot = await self._make_lot(status=status)
        manager = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])

        with pytest.raises(LotStructureLockedError):
            await self._use_case().execute(
                manager, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
            )

        assert self.demand_repo.demands == {}
        assert self.uow.committed is False

    async def test_open_demand_requires_confirmation(self):
        demand = await self.demand_repo.save(
            make_source_item_demand(
                id=1, lot_id=1, status=SourceItemDemandStatus.OPEN, source_item_id=1
            )
        )
        lot = await self._make_lot(
            input_demand_id=demand.id, source_item_id=1, source_bought_item_id=None
        )
        use_case = self._use_case()
        with pytest.raises(LotHasOpenDemandError):
            await use_case.execute(
                self.actor, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
            )
        # Unconfirmed attempt must not have touched anything.
        assert (await self.demand_repo.get_by_id(1)).canceled_at is None
        assert self.uow.committed is False

    async def test_open_demand_replaced_when_confirmed(self):
        demand = await self.demand_repo.save(
            make_source_item_demand(
                id=1, lot_id=1, status=SourceItemDemandStatus.OPEN, source_item_id=1
            )
        )
        lot = await self._make_lot(
            input_demand_id=demand.id, source_item_id=1, source_bought_item_id=None
        )
        use_case = self._use_case()
        result = await use_case.execute(
            self.actor,
            lot.id,
            SwitchLotMaterialSourceCommand(bought_item_id=1, confirm_replace_demand=True),
        )
        assert (await self.demand_repo.get_by_id(1)).canceled_at is not None
        assert result.input_demand_id is not None
        assert result.input_demand_id != 1
        new_demand = await self.demand_repo.get_by_id(result.input_demand_id)
        assert new_demand.bought_item_id == 1
        assert new_demand.canceled_at is None
        assert self.uow.committed is True

    async def _lot_with_demand(self, status: SourceItemDemandStatus, quantity: float = 10.0):
        demand = await self.demand_repo.save(
            make_source_item_demand(id=1, lot_id=1, status=status, source_item_id=1)
        )
        demand.quantity = quantity
        await self.demand_repo.save(demand)
        return await self._make_lot(
            input_demand_id=demand.id, source_item_id=1, source_bought_item_id=None
        )

    async def test_a_placed_demand_asks_before_it_is_replaced(self):
        lot = await self._lot_with_demand(SourceItemDemandStatus.ORDERED)

        with pytest.raises(LotHasPlacedDemandError):
            await self._use_case().execute(
                self.actor, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
            )
        assert (await self.demand_repo.get_by_id(1)).canceled_at is None
        assert self.uow.committed is False

    async def test_a_placed_demand_nothing_reached_is_replaced_whole(self):
        lot = await self._lot_with_demand(SourceItemDemandStatus.ORDERED)

        result = await self._use_case().execute(
            self.actor,
            lot.id,
            SwitchLotMaterialSourceCommand(bought_item_id=1, confirm_replace_demand=True),
        )

        assert (await self.demand_repo.get_by_id(1)).canceled_at is not None
        new_demand = await self.demand_repo.get_by_id(result.input_demand_id)
        assert new_demand.bought_item_id == 1
        assert new_demand.quantity == lot.quantity

    async def test_a_placed_demand_keeps_what_arrived_and_the_rest_moves(self):
        lot = await self._lot_with_demand(SourceItemDemandStatus.ALLOCATED, quantity=10.0)
        use_case = self._use_case()
        # Four pieces came from stock, which no line release touches.
        use_case._allocations.allocations.append(  # type: ignore[attr-defined]
            SimpleNamespace(id=7, demand_item_id=1, order_item_id=None, quantity=4.0)
        )

        result = await use_case.execute(
            self.actor,
            lot.id,
            SwitchLotMaterialSourceCommand(bought_item_id=1, confirm_replace_demand=True),
        )

        old = await self.demand_repo.get_by_id(1)
        assert old.canceled_at is None
        assert old.fulfilled_manually_at is not None
        new_demand = await self.demand_repo.get_by_id(result.input_demand_id)
        assert (new_demand.bought_item_id, new_demand.quantity) == (1, 6.0)

    async def test_a_fulfilled_demand_leaves_nothing_to_switch(self):
        lot = await self._lot_with_demand(SourceItemDemandStatus.FULFILLED)

        with pytest.raises(LotRawMaterialAlreadyLinkedError, match="all arrived"):
            await self._use_case().execute(
                self.actor,
                lot.id,
                SwitchLotMaterialSourceCommand(bought_item_id=1, confirm_replace_demand=True),
            )

    async def test_a_switch_from_a_stale_view_is_refused(self):
        lot = await self._make_lot()

        with pytest.raises(ConcurrentModificationError):
            await self._use_case().execute(
                self.actor,
                lot.id,
                SwitchLotMaterialSourceCommand(
                    bought_item_id=1, expected_edit_version=lot.edit_version + 1
                ),
            )
        assert self.uow.committed is False

    async def test_switching_to_rework_creates_no_demand(self):
        lot = await self._make_lot()
        use_case = self._use_case()
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(made_item_id=1)
        )
        assert result.source_made_item_id == 1
        assert result.input_demand_id is None

    async def test_clearing_source_entirely_creates_no_demand(self):
        lot = await self._make_lot()
        use_case = self._use_case()
        result = await use_case.execute(self.actor, lot.id, SwitchLotMaterialSourceCommand())
        assert result.source_bought_item_id is None
        assert result.source_item_id is None
        assert result.input_demand_id is None

    async def test_recompute_is_called_exactly_once_on_success(self):
        lot = await self._make_lot()
        recompute = FakeRecomputeMachineSchedule()
        use_case = self._use_case(recompute)
        await use_case.execute(self.actor, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1))
        assert recompute.calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        class FailingRecomputeSchedule:
            def __init__(self) -> None:
                self.attempts = 0

            async def execute_all(self, response_time_days=None, settings=None):
                self.attempts += 1
                raise RuntimeError("scheduling service is down")

        lot = await self._make_lot()
        recompute = FailingRecomputeSchedule()
        use_case = self._use_case(recompute)
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
        )
        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert result.input_demand_id is not None
