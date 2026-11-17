"""
Unit tests for TestLotPositionProvision, TestLotEventAuditTrail and
TestGetLotDemands. No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import (
    RecordLotPositionProvisionCommand,
)
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_demands import (
    GetLotDemands,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_events import GetLotEvents
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    GetLotPositionProvisions,
)
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    RecordLotPositionProvision,
)
from src.modules.fulfillment.application.use_cases.production_lot.update_lot import UpdateLot
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionProvisionOverflowError
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_order.fakes import lifecycle_collaborators


class TestLotPositionProvision:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

        self.lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-PROV",
                quantity=10.0,
                status=LotStatus.PARTIALLY_PLANNED,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        # Position 2 (EXTERNAL), its available input is position 1's
        # quantity_completed.
        self.position_1 = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.PARTIALLY_COMPLETED,
                quantity=10.0,
                quantity_completed=6.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        self.position_2 = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.EXTERNAL,
                status=LotPositionStatus.PENDING,
                quantity=10.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        self.use_case = RecordLotPositionProvision(self.lot_repo, uow=FakeUnitOfWork())

    async def test_records_provision_within_available_input(self):
        result = await self.use_case.execute(
            self.actor,
            self.lot.id,
            self.position_2.id,
            RecordLotPositionProvisionCommand(quantity=4.0, provision_date=date(2026, 1, 2)),
        )
        assert result.quantity == 4.0
        assert len(await self.lot_repo.get_provisions(self.position_2.id)) == 1

    async def test_reads_the_lot_with_a_row_lock(self):
        """Two concurrent provisions against the same lot must not
        both read the pre-insert existing_total, see
        IProductionLotRepository.get_by_id_for_update."""
        await self.use_case.execute(
            self.actor,
            self.lot.id,
            self.position_2.id,
            RecordLotPositionProvisionCommand(quantity=4.0, provision_date=date(2026, 1, 2)),
        )
        assert self.lot_repo.for_update_calls == [self.lot.id]

    async def test_rejects_provision_exceeding_predecessor_output(self):
        with pytest.raises(LotPositionProvisionOverflowError):
            await self.use_case.execute(
                self.actor,
                self.lot.id,
                self.position_2.id,
                RecordLotPositionProvisionCommand(quantity=7.0, provision_date=date(2026, 1, 2)),
            )

    async def test_rejects_provision_once_cumulative_exceeds_available(self):
        await self.use_case.execute(
            self.actor,
            self.lot.id,
            self.position_2.id,
            RecordLotPositionProvisionCommand(quantity=5.0, provision_date=date(2026, 1, 2)),
        )
        with pytest.raises(LotPositionProvisionOverflowError):
            await self.use_case.execute(
                self.actor,
                self.lot.id,
                self.position_2.id,
                RecordLotPositionProvisionCommand(quantity=2.0, provision_date=date(2026, 1, 2)),
            )

    async def test_rejects_provision_on_non_external_position(self):
        with pytest.raises(Exception):  # noqa: B017, LotPositionNotAssignableError
            await self.use_case.execute(
                self.actor,
                self.lot.id,
                self.position_1.id,
                RecordLotPositionProvisionCommand(quantity=1.0, provision_date=date(2026, 1, 2)),
            )

    async def test_get_provisions_lists_recorded_rows(self):
        await self.use_case.execute(
            self.actor,
            self.lot.id,
            self.position_2.id,
            RecordLotPositionProvisionCommand(quantity=3.0, provision_date=date(2026, 1, 2)),
        )
        get_use_case = GetLotPositionProvisions(self.lot_repo)
        results = await get_use_case.execute(self.lot.id, self.position_2.id)
        assert len(results) == 1

    async def test_requires_write_lots(self):
        permissionless = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                permissionless,
                self.lot.id,
                self.position_2.id,
                RecordLotPositionProvisionCommand(quantity=3.0, provision_date=date(2026, 1, 2)),
            )
        assert await self.lot_repo.get_provisions(self.position_2.id) == []


class TestLotEventAuditTrail:
    """End-to-end: a sequence of lifecycle actions on one lot should
    accumulate a matching, chronologically-ordered LotEvent trail,
    retrievable via GetLotEvents, the ISO 9001 read path."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.order_repo = FakeProductionOrderRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])

        made_item = make_made_item(processes=[])
        create_use_case = CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=FakeMadeItemRepository([made_item]),
            demand_repo=FakeMadeItemDemandRepository(),
            allocation_repo=FakeMadeItemAllocationRepository(),
            settings_repo=FakeAdminSettingsRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            order_repo=self.order_repo,
            inspection_method_repo=FakeInspectionMethodRepository(),
            machine_repo=FakeProductionMachineRepository(),
            uow=self.uow,
            event_bus=FakeEventBus(),
            reconciler=lot_reconciler(self.lot_repo, self.order_repo),
        )
        self.lot_id = (
            await create_use_case.execute(
                self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
            )
        ).id

    async def test_update_and_cancel_append_events_in_order(self):
        # DRAFT (zero positions) only legally transitions to
        # PARTIALLY_PLANNED/PLANNED/CANCELED (lot_status.py). CancelLot
        # is the simplest terminal action available from this state.
        await UpdateLot(
            lot_repo=self.lot_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        ).execute(self.actor, self.lot_id, UpdateLotCommand(note="updated note"))
        await CancelLot(
            lot_repo=self.lot_repo,
            order_repo=self.order_repo,
            order_item_repo=FakeOrderItemRepository(),
            allocation_repo=FakeBoughtItemAllocationRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=FakeOrderRepository([]),
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, self.lot_id, CancelLotCommand(reason="no longer needed"))

        events = await GetLotEvents(self.lot_repo).execute(self.lot_id)
        assert [e.event_type for e in events] == [
            LotEventType.LOT_CREATED,
            LotEventType.LOT_UPDATED,
            LotEventType.LOT_CANCELED,
        ]
        assert all(e.lot_id == self.lot_id for e in events)
        assert all(e.actor_username == self.actor.username for e in events)
        assert all(e.actor_full_name == self.actor.full_name for e in events)
        # occurred_at is monotonically non-decreasing across the sequence.
        assert [e.occurred_at for e in events] == sorted(e.occurred_at for e in events)

    async def test_get_events_raises_for_unknown_lot(self):
        with pytest.raises(LotNotFoundError):
            await GetLotEvents(self.lot_repo).execute(999)


class TestGetLotDemands:
    """The made-item demand(s) a lot was raised to cover: the reverse
    lookup from MadeItemDemandAllocation.lot_id, used by the lot detail
    view's traceability section."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

        made_item = make_made_item(processes=[])
        create_use_case = CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=FakeMadeItemRepository([made_item]),
            demand_repo=FakeMadeItemDemandRepository(),
            allocation_repo=FakeMadeItemAllocationRepository(),
            settings_repo=FakeAdminSettingsRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            order_repo=FakeProductionOrderRepository(),
            inspection_method_repo=FakeInspectionMethodRepository(),
            machine_repo=FakeProductionMachineRepository(),
            uow=FakeUnitOfWork(),
            event_bus=FakeEventBus(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        self.lot_id = (
            await create_use_case.execute(
                self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=8.0)
            )
        ).id

    async def test_returns_demands_allocated_to_the_lot(self):
        demand_a = make_demand(id=1, quantity=5.0, item_article_name="Bracket")
        demand_b = make_demand(id=2, quantity=3.0, item_article_name="Housing")
        demand_repo = FakeMadeItemDemandRepository([demand_a, demand_b])
        allocation_repo = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=self.lot_id,
                    quantity=5.0,
                    source=MadeItemAllocationSource.LOT,
                ),
                MadeItemDemandAllocation(
                    demand_item_id=2,
                    lot_id=self.lot_id,
                    quantity=3.0,
                    source=MadeItemAllocationSource.LOT,
                ),
                # A demand allocated to a DIFFERENT lot must not leak in.
                MadeItemDemandAllocation(
                    demand_item_id=3, lot_id=999, quantity=1.0, source=MadeItemAllocationSource.LOT
                ),
            ]
        )

        results = await GetLotDemands(
            lot_repo=self.lot_repo,
            made_item_allocation_repo=allocation_repo,
            made_item_demand_repo=demand_repo,
        ).execute(self.lot_id)

        assert {r.id for r in results} == {1, 2}
        by_id = {r.id: r for r in results}
        assert by_id[1].allocated_quantity == 5.0
        assert by_id[1].item_article_name == "Bracket"
        assert by_id[2].allocated_quantity == 3.0

    async def test_returns_empty_when_lot_has_no_demand_allocations(self):
        results = await GetLotDemands(
            lot_repo=self.lot_repo,
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
        ).execute(self.lot_id)

        assert results == []

    async def test_raises_for_unknown_lot(self):
        with pytest.raises(LotNotFoundError):
            await GetLotDemands(
                lot_repo=self.lot_repo,
                made_item_allocation_repo=FakeMadeItemAllocationRepository(),
                made_item_demand_repo=FakeMadeItemDemandRepository(),
            ).execute(999)
