"""
Unit tests for TestAutoAssignLots. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.production_lot_dto import (
    AutoAssignLotGroupDemandResult,
)
from src.modules.fulfillment.application.use_cases.production_lot.auto_assign_lots import (
    AutoAssignLots,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestAutoAssignLots:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.settings_repo = FakeAdminSettingsRepository()
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.order_repo = FakeProductionOrderRepository()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _use_case(
        self, made_item: MadeItem, create_lot: CreateLot | None = None, recompute_schedule=None
    ) -> AutoAssignLots:
        reconciler = lot_reconciler(
            self.lot_repo,
            self.order_repo,
            made_demands=self.demand_repo,
            made_allocations=self.allocation_repo,
        )
        if create_lot is None:
            create_lot = CreateLot(
                lot_repo=self.lot_repo,
                made_item_repo=FakeMadeItemRepository([made_item]),
                demand_repo=self.demand_repo,
                allocation_repo=self.allocation_repo,
                settings_repo=self.settings_repo,
                source_item_demand_repo=self.source_item_demand_repo,
                order_repo=self.order_repo,
                inspection_method_repo=self.inspection_method_repo,
                machine_repo=self.machine_repo,
                uow=self.uow,
                event_bus=FakeEventBus(),
                reconciler=reconciler,
            )
        # AutoAssignLots owns the transaction and the publishing, so it
        # takes a uow and an event bus of its own, and runs the reconciler
        # its CreateLot registers the new lots with.
        return AutoAssignLots(
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            lot_repo=self.lot_repo,
            create_lot=create_lot,
            uow=self.uow,
            event_bus=self.bus,
            reconciler=reconciler,
            recompute_schedule=recompute_schedule,
        )

    async def test_the_new_lots_request_one_schedule_walk(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1),
                make_demand(id=2, quantity=2.0, made_item_id=1, project_id=2),
            ]
        )
        recompute = FakeRecomputeMachineSchedule()

        results = await self._use_case(made_item, recompute_schedule=recompute).execute(self.actor)

        assert len(results) == 2
        assert recompute.calls == 1

    async def test_groups_same_project_and_item_into_one_lot(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1),
                make_demand(id=2, quantity=2.0, made_item_id=1, project_id=1),
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert len(results) == 1
        assert results[0].quantity == 5.0
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"
        assert (await self.demand_repo.get_by_id(2)).status == "allocated"
        assert self.uow.committed is True

    async def test_commits_exactly_once_for_multiple_groups(self):
        """The whole sweep is one transaction, not one commit per group."""
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1),
                make_demand(id=2, quantity=2.0, made_item_id=1, project_id=2),
                make_demand(id=3, quantity=4.0, made_item_id=1, project_id=3),
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert len(results) == 3
        assert self.uow.commits == 1

    async def test_no_lot_is_persisted_when_a_later_group_raises(self):
        """All-or-nothing: a failure on group 2 must not leave group 1's lot
        behind, and must never reach the commit."""

        class _FailingCreateLot:
            def __init__(self) -> None:
                self.calls = 0

            async def lock_routing_queue_scopes(self, made_item_ids):
                return None

            async def create_no_commit(self, actor, cmd):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("group 2 exploded")
                return

        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1),
                make_demand(id=2, quantity=2.0, made_item_id=1, project_id=2),
            ]
        )
        use_case = self._use_case(make_made_item(processes=[]), create_lot=_FailingCreateLot())

        with pytest.raises(RuntimeError):
            await use_case.execute(self.actor)

        assert self.uow.commits == 0
        assert self.lot_repo.lots == {}
        assert self.bus.published == []

    async def test_publishes_one_lot_created_per_group_after_the_commit(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1),
                make_demand(id=2, quantity=2.0, made_item_id=1, project_id=2),
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        created = [e for e in self.bus.published if isinstance(e, LotCreated)]
        assert len(created) == len(results) == 2
        assert {e.lot_id for e in created} == {r.id for r in results}

    async def test_different_projects_create_separate_lots(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1),
                make_demand(id=2, quantity=2.0, made_item_id=1, project_id=2),
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert len(results) == 2
        assert {r.quantity for r in results} == {3.0, 2.0}

    async def test_fully_allocated_demand_is_skipped(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        self.allocation_repo = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=None,
                    quantity=5.0,
                    source=MadeItemAllocationSource.STOCK,
                )
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert results == []

    async def test_partially_allocated_demand_only_covers_remainder(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, status=MadeItemDemandStatus.ALLOCATED)]
        )
        self.allocation_repo = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=None,
                    quantity=2.0,
                    source=MadeItemAllocationSource.STOCK,
                )
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert len(results) == 1
        assert results[0].quantity == 3.0

    async def test_canceled_and_fulfilled_demand_excluded(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=5.0, status=MadeItemDemandStatus.CANCELED),
                make_demand(id=2, quantity=5.0, status=MadeItemDemandStatus.FULFILLED),
            ]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert results == []

    async def test_preview_does_not_create_lots(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, item_part_number="PN-AUTOASSIGN", item_revision="D")]
        )
        use_case = self._use_case(made_item)

        groups = await use_case.preview(self.actor)

        assert len(groups) == 1
        assert groups[0].quantity == 5.0
        assert groups[0].item_part_number == "PN-AUTOASSIGN"
        # item_revision: denormalized alongside item_part_number.
        assert groups[0].item_revision == "D"
        assert groups[0].demands == [AutoAssignLotGroupDemandResult(demand_item_id=1, quantity=5.0)]
        assert (await self.demand_repo.get_by_id(1)).status == "open"
        assert await self.lot_repo.get_by_id(1) is None

    async def test_high_priority_demand_marks_group_high_priority(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, high_priority=False),
                make_demand(id=2, quantity=2.0, high_priority=True),
            ]
        )
        use_case = self._use_case(made_item)

        groups = await use_case.preview(self.actor)

        assert len(groups) == 1
        assert groups[0].high_priority is True

    async def test_unprivileged_actor_cannot_auto_assign(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        use_case = self._use_case(made_item)
        actor = make_user(permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor)

    async def test_group_takes_earliest_delivery_date_among_its_demands(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, desired_delivery_date=date(2026, 9, 10)),
                make_demand(id=2, quantity=2.0, desired_delivery_date=date(2026, 8, 30)),
            ]
        )
        use_case = self._use_case(made_item)

        groups = await use_case.preview(self.actor)

        assert len(groups) == 1
        assert groups[0].required_delivery_date == date(2026, 8, 30)

    async def test_group_delivery_date_ignores_demands_without_one(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=3.0, desired_delivery_date=None),
                make_demand(id=2, quantity=2.0, desired_delivery_date=date(2026, 8, 30)),
            ]
        )
        use_case = self._use_case(made_item)

        groups = await use_case.preview(self.actor)

        assert len(groups) == 1
        assert groups[0].required_delivery_date == date(2026, 8, 30)

    async def test_group_delivery_date_is_none_when_no_demand_has_one(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        use_case = self._use_case(made_item)

        groups = await use_case.preview(self.actor)

        assert groups[0].required_delivery_date is None

    async def test_created_lot_carries_the_group_delivery_date(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, desired_delivery_date=date(2026, 8, 30))]
        )
        use_case = self._use_case(made_item)

        results = await use_case.execute(self.actor)

        assert len(results) == 1
        assert results[0].required_delivery_date == date(2026, 8, 30)


class TestAutoAssignSweepLock:
    """The sweep links its demands lot by lot. A later group can hold lower
    demand ids than an earlier one, so every demand of the sweep is locked
    in one acquisition before the first lot; locking them group by group
    would request a lower id after a higher one and break the one lock
    order."""

    async def test_a_later_group_with_lower_demand_ids_is_linked_in_the_same_sweep(self):
        lot_repo = FakeProductionLotRepository()
        # An existing lot already covers one piece of demand 4.
        lot_repo._lots[1] = ProductionLot(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=1.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        lot_repo._next_lot_id = 2
        # Inserted so the group of made item 1 (demands 3 and 4) comes first
        # and the group of made item 2 (demands 1 and 2) second.
        demands = FakeMadeItemDemandRepository(
            [
                make_demand(id=3, quantity=2.0, made_item_id=1, project_id=1),
                make_demand(
                    id=4,
                    quantity=4.0,
                    made_item_id=1,
                    project_id=1,
                    status=MadeItemDemandStatus.ALLOCATED,
                ),
                make_demand(id=1, quantity=2.0, made_item_id=2, project_id=1),
                make_demand(id=2, quantity=1.0, made_item_id=2, project_id=1),
            ]
        )
        allocations = FakeMadeItemAllocationRepository(
            [MadeItemDemandAllocation(demand_item_id=4, lot_id=1, quantity=1.0)]
        )
        order_repo = FakeProductionOrderRepository()
        uow = FakeUnitOfWork()
        harness_reconciler = lot_reconciler(
            lot_repo, order_repo, made_demands=demands, made_allocations=allocations
        )
        create_lot = CreateLot(
            lot_repo=lot_repo,
            made_item_repo=FakeMadeItemRepository(
                [make_made_item(id=1, processes=[]), make_made_item(id=2, processes=[])]
            ),
            demand_repo=demands,
            allocation_repo=allocations,
            settings_repo=FakeAdminSettingsRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            order_repo=order_repo,
            inspection_method_repo=FakeInspectionMethodRepository(),
            machine_repo=FakeProductionMachineRepository(),
            uow=uow,
            event_bus=FakeEventBus(),
            reconciler=harness_reconciler,
        )
        use_case = AutoAssignLots(
            demand_repo=demands,
            allocation_repo=allocations,
            lot_repo=lot_repo,
            create_lot=create_lot,
            uow=uow,
            event_bus=FakeEventBus(),
            reconciler=harness_reconciler,
        )

        results = await use_case.execute(make_user(permissions=[Permission.WRITE_LOTS]))

        assert sorted((r.made_item_id, r.quantity) for r in results) == [(1, 5.0), (2, 3.0)]
        for demand_id in (1, 2, 3, 4):
            demand = await demands.get_by_id(demand_id)
            assert demand is not None and demand.status == "allocated"
        assert uow.commits == 1
