"""
Unit tests for TestCreateLot. No database, no HTTP. All dependencies
replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import LotAlterationSourceConflictError
from src.modules.fulfillment.domain.errors import LotDemandMadeItemMismatchError
from src.modules.fulfillment.domain.errors import LotDemandProjectMismatchError
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_inspection_method
from tests.unit.production_lot._helpers import make_machine
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
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestCreateLot:
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

    def _use_case(self, made_item: MadeItem, recompute_schedule=None) -> CreateLot:
        """Lot creation with a reconciler that reads the lot, production
        order, made demand and made allocation fakes, so a linked demand
        shows the status its derivation gives and the harness records what
        the lock plan acquired."""
        self.harness = demand_reconciler_harness(
            lots=self.lot_repo,
            production_orders=self.order_repo,
            made_demands=self.demand_repo,
            made_allocations=self.allocation_repo,
        )
        return CreateLot(
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
            event_bus=self.bus,
            reconciler=self.harness.reconciler,
            recompute_schedule=recompute_schedule,
        )

    async def test_a_new_lot_requests_one_schedule_walk(self):
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        recompute = FakeRecomputeMachineSchedule()

        await self._use_case(made_item, recompute).execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert recompute.calls == 1

    async def test_publishes_lot_created(self):
        # Without this the lot_created print trigger can never fire, and
        # nothing else in the system notices a new lot either: the event
        # class and its EVENT_REGISTRY entry existed for a long time with
        # no publisher behind them.
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        result = await self._use_case(made_item).execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        published = [e for e in self.bus.published if isinstance(e, LotCreated)]
        assert len(published) == 1
        assert published[0].lot_id == result.id
        assert published[0].made_item_id == made_item.id

    async def test_publishes_lot_created_inside_the_transaction_before_the_commit(self):
        # With the transactional outbox, publish() stages a row in the
        # caller's own session, so it must run BEFORE the commit that makes
        # it durable, since a row staged afterwards is never committed by
        # anyone and the event is silently lost.
        #
        # A subscriber never observes a lot that a later failure rolled
        # back, because the rollback that discards the lot discards the
        # staged event with it, and a crash after the commit cannot lose
        # the event.
        #
        # Both fakes append to one log, which is what makes the ordering
        # assertable at all.
        sequence: list[str] = []

        class SequencedUnitOfWork:
            async def commit(self) -> None:
                sequence.append("commit")

            async def rollback(self) -> None:
                pass

        class SequencedEventBus:
            async def publish(self, event: object) -> None:
                sequence.append(f"publish:{type(event).__name__}")

        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        await CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=FakeMadeItemRepository([made_item]),
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            settings_repo=self.settings_repo,
            source_item_demand_repo=self.source_item_demand_repo,
            order_repo=self.order_repo,
            inspection_method_repo=self.inspection_method_repo,
            machine_repo=self.machine_repo,
            uow=SequencedUnitOfWork(),
            event_bus=SequencedEventBus(),
            reconciler=lot_reconciler(self.lot_repo, self.order_repo),
        ).execute(self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0))

        assert sequence == ["publish:LotCreated", "commit"]

    async def test_snapshots_each_process_into_its_own_position(self):
        made_item = make_made_item(
            processes=[make_process(id=1, position=0), make_process(id=2, position=1)]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert result.status == "draft"
        assert len(result.positions) == 2
        assert [p.kind for p in result.positions] == ["unassigned", "unassigned"]
        assert [len(p.steps) for p in result.positions] == [1, 1]
        assert result.positions[0].steps[0].source_process_id == 1
        assert result.positions[1].steps[0].source_process_id == 2
        assert [p.sequence for p in result.positions] == [1, 2]

    async def test_snapshots_grouped_processes_into_shared_position(self):
        made_item = make_made_item(
            processes=[
                make_process(id=1, position=0, group_index=0),
                make_process(id=2, position=1, group_index=0),
                make_process(id=3, position=2, group_index=1),
            ]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert len(result.positions) == 2
        assert [len(p.steps) for p in result.positions] == [2, 1]
        assert [s.source_process_id for s in result.positions[0].steps] == [1, 2]
        assert [s.sequence for s in result.positions[0].steps] == [1, 2]
        assert result.positions[1].steps[0].source_process_id == 3
        assert result.positions[1].steps[0].sequence == 3
        assert [p.sequence for p in result.positions] == [1, 2]

    async def test_zero_processes_creates_no_positions(self):
        made_item = make_made_item(processes=[])
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert result.positions == []
        assert result.steps == []

    async def test_inspection_process_snapshots_into_its_own_position(self):
        made_item = make_made_item(
            processes=[
                make_process(id=1, position=0, group_index=0),
                make_process(id=2, position=1, group_index=0),
                make_process(
                    id=3,
                    position=2,
                    group_index=1,
                    fabrication_method_id=None,
                    role=StepRole.INSPECTION,
                    inspection_method_id=1,
                ),
            ]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert len(result.positions) == 2
        assert [len(p.steps) for p in result.positions] == [2, 1]
        inspection_step = result.positions[1].steps[0]
        assert inspection_step.role == "inspection"
        assert inspection_step.inspection_method_id == 1
        assert inspection_step.fabrication_method_id is None
        # Born internal: a catalogue-routed inspection position gets its
        # one machine-less QUEUED production order the moment the lot is
        # created, same as the auto-appended require_qa position below.
        inspection_position = result.positions[1]
        assert inspection_position.kind == "internal"
        assert len(inspection_position.production_orders) == 1
        auto_order = inspection_position.production_orders[0]
        assert auto_order.machine_id is None
        assert auto_order.machine_pool_id is None
        assert auto_order.status == "queued"
        assert auto_order.quantity == inspection_position.quantity
        # The fabrication position is untouched: still unassigned, no orders.
        assert result.positions[0].kind == "unassigned"
        assert result.positions[0].production_orders == []

    async def test_require_qa_appends_trailing_visual_qa_position(self):
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        made_item = make_made_item(
            processes=[make_process(id=1, position=0), make_process(id=2, position=1)]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert len(result.positions) == 3
        qa_position = result.positions[-1]
        assert qa_position.sequence == 3
        assert len(qa_position.steps) == 1
        qa_step = qa_position.steps[0]
        assert qa_step.role == "inspection"
        assert qa_step.inspection_method_id == 1
        assert qa_step.fabrication_method_id is None
        assert qa_step.source_process_id is None
        assert qa_step.estimated_setup_minutes is None
        assert qa_step.estimated_minutes_per_piece is None
        # Born internal: no kanban card / permanent "not planned"
        # for a require_qa-appended position either.
        assert qa_position.kind == "internal"
        assert len(qa_position.production_orders) == 1
        assert qa_position.production_orders[0].machine_id is None
        assert qa_position.production_orders[0].status == "queued"

    async def test_default_machine_prefills_the_appended_qa_orders_machine_id(self):
        """The core of the default-machine feature: an inspection method
        with default_machine_id configured pre-fills that machine onto the
        auto-queued order for a lot born under require_qa, so the QA step
        stops being generically machine-less."""
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1, default_machine_id=9)]
        )
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=9, is_qa_machine=True)]
        )
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        qa_position = result.positions[-1]
        assert qa_position.production_orders[0].machine_id == 9

    async def test_method_with_no_default_machine_leaves_the_qa_order_machine_less(self):
        # FakeInspectionMethodRepository()'s seeded method (id=1) has
        # default_machine_id=None (make_inspection_method's own default),
        # the setup_method baseline, no override needed.
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert result.positions[-1].production_orders[0].machine_id is None

    async def test_soft_deleted_default_machine_falls_back_to_machine_less(self):
        """An invalid default at creation time degrades to machine-less
        rather than blocking lot creation. Hard validation of the default
        lives at write time on the inspection method instead (see
        test_inspection_method_use_cases.py)."""
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1, default_machine_id=9)]
        )
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=9, is_qa_machine=True, archived=True)]
        )
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert result.positions[-1].production_orders[0].machine_id is None

    async def test_default_machine_no_longer_qa_falls_back_to_machine_less(self):
        """The other failure mode: the default machine still exists but
        was un-flagged is_qa_machine since the method was configured.
        Degrades the same way, no raise."""
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1, default_machine_id=9)]
        )
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=9, is_qa_machine=False)]
        )
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert result.positions[-1].production_orders[0].machine_id is None

    async def test_catalogue_routed_inspection_position_honours_its_methods_default(self):
        """The pre-fill isn't only for the require_qa trailing append: a
        catalogue-routed inspection process (MadeItemProcess.
        inspection_method_id) resolves its own method's default too, via
        the same _resolve_default_machine_id path."""
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1, default_machine_id=9)]
        )
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=9, is_qa_machine=True)]
        )
        made_item = make_made_item(
            processes=[
                make_process(id=1, position=0, group_index=0),
                make_process(
                    id=2,
                    position=1,
                    group_index=1,
                    fabrication_method_id=None,
                    role=StepRole.INSPECTION,
                    inspection_method_id=1,
                ),
            ]
        )
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        inspection_position = result.positions[1]
        assert inspection_position.production_orders[0].machine_id == 9

    async def test_the_appended_qa_step_inherits_the_methods_default_durations(self):
        """The auto-appended step has no catalogue process to inherit
        estimates from, so the method is the only place they can come from.
        Without this the QA order is sized 0 and consumes no shop
        capacity."""
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(id=1, default_setup_minutes=10, default_minutes_per_piece=2.5)]
        )
        made_item = make_made_item(processes=[make_process(id=1, position=0)])
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=4.0)
        )

        qa_step = result.positions[-1].steps[0]
        assert qa_step.estimated_setup_minutes == 10
        assert qa_step.estimated_minutes_per_piece == 2.5
        # and the born-internal order is sized from them: 10 + 4 * 2.5
        order = result.positions[-1].production_orders[0]
        assert order.estimated_duration_minutes == 20

    async def test_require_qa_is_a_noop_when_routing_already_ends_with_inspection(self):
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        made_item = make_made_item(
            processes=[
                make_process(id=1, position=0, group_index=0),
                make_process(
                    id=2,
                    position=1,
                    group_index=1,
                    fabrication_method_id=None,
                    role=StepRole.INSPECTION,
                    inspection_method_id=2,
                ),
            ]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert len(result.positions) == 2
        assert result.positions[-1].steps[0].inspection_method_id == 2
        assert result.positions[-1].kind == "internal"
        assert len(result.positions[-1].production_orders) == 1

    async def test_require_qa_with_zero_processes_creates_one_qa_position(self):
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        made_item = make_made_item(processes=[])
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert len(result.positions) == 1
        assert len(result.steps) == 1
        assert result.steps[0].role == "inspection"
        assert result.steps[0].inspection_method_id == 1
        assert result.positions[0].kind == "internal"
        assert len(result.positions[0].production_orders) == 1
        assert result.positions[0].production_orders[0].machine_id is None

    async def test_no_inspection_step_creates_no_production_order(self):
        made_item = make_made_item(
            processes=[make_process(id=1, position=0), make_process(id=2, position=1)]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert all(p.kind == "unassigned" for p in result.positions)
        assert all(p.production_orders == [] for p in result.positions)

    async def test_priority_prefilled_from_high_priority_demand(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, high_priority=True)]
        )
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )
        assert result.priority == "high"

    async def test_demand_allocation_moves_demand_to_allocated(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        use_case = self._use_case(made_item)
        await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"
        assert self.uow.committed is True

    async def test_demand_allocation_reads_the_demand_with_a_row_lock(self):
        """Two concurrent lots linking to the same demand must not both read
        the pre-insert existing_total, so the lock plan acquires the demand
        before the allocations are read."""
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        use_case = self._use_case(made_item)
        await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )
        made_locks = [
            ids
            for aggregate, ids in self.harness.lock_log
            if aggregate is LifecycleAggregate.MADE_DEMANDS
        ]
        assert made_locks == [(1,)]

    async def test_the_lot_number_is_drawn_after_the_demands_are_locked(self):
        """A number's counter row is a lock outside the lifecycle lock order,
        so it is drawn only after the lifecycle locks; a creation that held
        it while waiting for a demand could close a cycle with a writer that
        holds the demand and then draws."""
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        use_case = self._use_case(made_item)
        locks_at_draw: list[list[LifecycleAggregate]] = []
        draw = self.lot_repo.next_lot_number

        async def recording_draw(template: str) -> str:
            locks_at_draw.append([aggregate for aggregate, _ in self.harness.lock_log])
            return await draw(template)

        self.lot_repo.next_lot_number = recording_draw  # type: ignore[method-assign]
        await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )

        assert locks_at_draw == [[LifecycleAggregate.MADE_DEMANDS]]

    async def test_a_demand_of_another_made_item_is_refused(self):
        """A lot covers demands of the made item it produces only; linking a
        demand of another item is refused before anything is written."""
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, made_item_id=2)]
        )
        use_case = self._use_case(made_item)

        with pytest.raises(LotDemandMadeItemMismatchError):
            await use_case.execute(
                self.actor,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=5.0,
                    demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
                ),
            )

        assert await self.allocation_repo.get_by_demand_item_id(1) == []
        assert self.uow.committed is False

    async def test_alteration_demand_sets_lot_source_made_item(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, is_alteration=True, alteration_of_made_item_id=99)]
        )
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )

        saved_lot = await self.lot_repo.get_by_id(result.id)
        assert saved_lot.source_made_item_id == 99
        assert saved_lot.is_alteration is True
        assert saved_lot.source_bought_item_id is None
        assert saved_lot.source_item_id is None

    async def test_alteration_lot_skips_source_item_demand_even_with_bought_source(self):
        made_item = make_made_item(processes=[], bought_item_id=7)
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, is_alteration=True, alteration_of_made_item_id=99)]
        )
        use_case = self._use_case(made_item)

        result = await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )

        saved_lot = await self.lot_repo.get_by_id(result.id)
        assert saved_lot.input_demand_id is None
        assert saved_lot.source_bought_item_id is None

    async def test_allocation_exceeding_lot_quantity_raises(self):
        """A demand for 14 dropped into a lot of 10 must be rejected, the
        allocation would otherwise report the demand fully covered by four
        pieces nobody is producing."""
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=14.0)])
        use_case = self._use_case(made_item)

        with pytest.raises(AllocationOverflowError):
            await use_case.execute(
                self.actor,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=10.0,
                    demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=14.0)],
                ),
            )
        assert self.uow.committed is False

    async def test_allocations_summing_over_lot_quantity_raises(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=6.0), make_demand(id=2, quantity=6.0)]
        )
        use_case = self._use_case(made_item)

        with pytest.raises(AllocationOverflowError):
            await use_case.execute(
                self.actor,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=10.0,
                    demand_allocations=[
                        LotDemandAllocationInput(demand_item_id=1, quantity=6.0),
                        LotDemandAllocationInput(demand_item_id=2, quantity=6.0),
                    ],
                ),
            )

    async def test_allocation_below_lot_quantity_is_allowed(self):
        """The reverse, a lot producing more than it allocates, is legal;
        the surplus simply goes to stock."""
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=14.0)])
        use_case = self._use_case(made_item)

        await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=14.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=10.0)],
            ),
        )
        assert (await self.allocation_repo.get_by_demand_item_id(1))[0].quantity == 10.0

    async def test_mixing_alteration_and_normal_demand_raises(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=2.0, is_alteration=True, alteration_of_made_item_id=99),
                make_demand(id=2, quantity=3.0, is_alteration=False),
            ]
        )
        use_case = self._use_case(made_item)

        with pytest.raises(LotAlterationSourceConflictError):
            await use_case.execute(
                self.actor,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=5.0,
                    demand_allocations=[
                        LotDemandAllocationInput(demand_item_id=1, quantity=2.0),
                        LotDemandAllocationInput(demand_item_id=2, quantity=3.0),
                    ],
                ),
            )

    async def test_conflicting_alteration_sources_raises(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository(
            [
                make_demand(id=1, quantity=2.0, is_alteration=True, alteration_of_made_item_id=98),
                make_demand(id=2, quantity=3.0, is_alteration=True, alteration_of_made_item_id=99),
            ]
        )
        use_case = self._use_case(made_item)

        with pytest.raises(LotAlterationSourceConflictError):
            await use_case.execute(
                self.actor,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=5.0,
                    demand_allocations=[
                        LotDemandAllocationInput(demand_item_id=1, quantity=2.0),
                        LotDemandAllocationInput(demand_item_id=2, quantity=3.0),
                    ],
                ),
            )

    async def test_demand_from_another_project_raises(self):
        made_item = make_made_item(processes=[])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        use_case = self._use_case(made_item)
        with pytest.raises(LotDemandProjectMismatchError):
            await use_case.execute(
                self.actor,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=2,
                    quantity=5.0,
                    demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
                ),
            )

    async def test_bought_item_source_auto_creates_source_item_demand(self):
        made_item = make_made_item(processes=[], bought_item_id=7)
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert result.input_demand_id is not None
        demand = await self.source_item_demand_repo.get_by_id(result.input_demand_id)
        assert demand is not None
        assert demand.bought_item_id == 7
        assert demand.source_item_id is None
        assert demand.quantity == 5.0
        assert demand.unit == "pcs"
        assert demand.lot_id == result.id

    async def test_source_item_source_auto_creates_source_item_demand(self):
        made_item = make_made_item(processes=[], source_item_id=9)
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert result.input_demand_id is not None
        demand = await self.source_item_demand_repo.get_by_id(result.input_demand_id)
        assert demand is not None
        assert demand.source_item_id == 9
        assert demand.bought_item_id is None

    async def test_no_source_creates_no_demand(self):
        made_item = make_made_item(processes=[])
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )
        assert result.input_demand_id is None

    async def test_passes_through_required_delivery_date(self):
        made_item = make_made_item(processes=[])
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                required_delivery_date=date(2026, 5, 1),
            ),
        )
        assert result.required_delivery_date == date(2026, 5, 1)

    async def test_records_a_lot_created_event(self):
        made_item = make_made_item(processes=[])
        use_case = self._use_case(made_item)
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        events = await self.lot_repo.get_events(result.id)
        assert len(events) == 1
        event = events[0]
        assert event.event_type == LotEventType.LOT_CREATED
        assert event.entity == "lot"
        assert event.lot_id == result.id
        assert event.actor_id == self.actor.id
        assert event.actor_username == self.actor.username
        assert event.payload == {"made_item_id": 1, "quantity": 5.0}
