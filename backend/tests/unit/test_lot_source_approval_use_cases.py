"""
Unit tests for the Source Item Approval Step: ApproveLotSource,
RejectLotSource, and the source_approval_status side effects grafted onto
CreateLot / SwitchLotMaterialSource / CreateSourceItemDemand /
UpdateProductionSettings. No database, no HTTP.

Fakes are reused from the existing unit test modules rather than
duplicated wholesale (the same cross-file-import precedent
test_admin_settings_get_use_cases.py already establishes for
tests/unit/admin_settings/fakes.py's fixtures). See
tests/unit/production_lot/ (fakes.py, _helpers.py),
tests/unit/test_source_item_demand_use_cases.py and
tests/unit/admin_settings/fakes.py. Two of them (the admin
settings repos) predate require_source_item_approval, so this file
subclasses them locally rather than editing those read-only files.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    UpdateProductionSettingsCommand,
)
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import RejectLotSourceCommand
from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    CreateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_production_settings import (
    UpdateProductionSettings,
)
from src.modules.fulfillment.application.use_cases.production_lot.approve_lot_source import (
    ApproveLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_lot.reject_lot_source import (
    RejectLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.create_source_item_demand import (
    CreateSourceItemDemand,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import LotRawMaterialAlreadyLinkedError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.errors import SourceApprovalNotPendingError
from src.modules.fulfillment.domain.errors import SourceItemApprovalRequiredError
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.errors import ProjectInactiveError
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository as SettingsRepoFake
from tests.unit.admin_settings.fakes import (
    FakeInspectionMethodRepository as SettingsInspectionMethodFake,
)
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot._helpers import make_bought_item
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_source_item
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemRepository
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository as ActiveProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemRepository
from tests.unit.production_lot.fakes import fake_line_release
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.test_source_item_demand_use_cases import FakeProjectRepository
from tests.unit.test_source_item_demand_use_cases import make_project

# ── Helpers ───────────────────────────────────────────────────────────


def make_lot(
    id: int = 0,
    quantity: float = 5.0,
    status: LotStatus = LotStatus.DRAFT,
    made_item_id: int = 1,
    project_id: int = 1,
    source_bought_item_id: int | None = None,
    source_item_id: int | None = 1,
    source_made_item_id: int | None = None,
    input_demand_id: int | None = None,
    source_approval_status: SourceApprovalStatus = SourceApprovalStatus.PENDING,
    source_approved_by_id: int | None = None,
    source_approved_date: datetime | None = None,
    source_rejected_by_id: int | None = None,
    source_rejected_date: datetime | None = None,
    source_rejection_reason: str | None = None,
) -> ProductionLot:
    return ProductionLot(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number=f"LOT-{id or 'NEW'}",
        quantity=quantity,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=made_item_id,
        project_id=project_id,
        input_demand_id=input_demand_id,
        source_bought_item_id=source_bought_item_id,
        source_item_id=source_item_id,
        source_made_item_id=source_made_item_id,
        source_approval_status=source_approval_status,
        source_approved_by_id=source_approved_by_id,
        source_approved_date=source_approved_date,
        source_rejected_by_id=source_rejected_by_id,
        source_rejected_date=source_rejected_date,
        source_rejection_reason=source_rejection_reason,
    )


class FakeRecomputeSchedule:
    """Fake of RecomputeMachineSchedule, see
    tests/unit/production_order/fakes.py's identical class."""

    def __init__(self) -> None:
        self.execute_all_calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.execute_all_calls += 1
        return []


class FailingRecomputeSchedule:
    def __init__(self) -> None:
        self.attempts: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.attempts += 1
        raise RuntimeError("scheduling service is down")


class ApprovalSettingsRepo(FakeAdminSettingsRepository):
    """FakeAdminSettingsRepository (tests/unit/production_lot/fakes.py)
    predates require_source_item_approval, so its get_production() always
    returns the entity's dataclass default (False). This subclass adds
    control over that one field without touching the read-only fixture
    file."""

    def __init__(self, require_source_item_approval: bool = False, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._require_source_item_approval = require_source_item_approval

    async def get_production(self) -> AdminProductionSettings:
        settings = await super().get_production()
        settings.require_source_item_approval = self._require_source_item_approval
        return settings


# ── ApproveLotSource ─────────────────────────────────────────────────


class TestApproveLotSource:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeSourceItemDemandRepository()
        self.project_repo = ActiveProjectRepository()
        self.source_item_repo = FakeSourceItemRepository([make_source_item(id=1)])
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.MANAGE_LOTS])

    def _use_case(self, recompute_schedule=None) -> ApproveLotSource:
        return ApproveLotSource(
            lot_repo=self.lot_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            recompute_schedule=recompute_schedule,
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
            project_repo=self.project_repo,
            source_item_repo=self.source_item_repo,
        )

    async def test_approves_a_pending_lot_creating_exactly_one_demand(self):
        lot = await self.lot_repo.save(
            make_lot(quantity=7.0, source_approval_status=SourceApprovalStatus.PENDING)
        )
        result = await self._use_case().execute(self.actor, lot.id)

        assert result.source_approval_status == SourceApprovalStatus.APPROVED.value
        assert result.source_approved_by_id == self.actor.id
        assert result.source_approved_date is not None
        assert result.source_rejected_by_id is None
        assert result.source_rejected_date is None
        assert result.source_rejection_reason is None
        assert result.input_demand_id is not None

        # Exactly one demand, using CreateLot._create_source_item_demand's
        # own defaults.
        assert len(self.demand_repo.demands) == 1
        demand = await self.demand_repo.get_by_id(result.input_demand_id)
        assert demand is not None
        assert demand.quantity == 7.0
        assert demand.unit == "pcs"
        assert demand.items_per_unit == 1.0
        assert demand.lot_id == lot.id
        assert demand.source_item_id == lot.source_item_id

        events = await self.lot_repo.get_events(lot.id)
        assert len(events) == 1
        assert events[0].event_type == LotEventType.LOT_SOURCE_APPROVED
        # Payload widened by the material-assignment feature: this use case
        # is built here without the made-item and settings repos, so the
        # write-back is reported as skipped_disabled.
        assert events[0].payload == {
            "source_item_demand_id": demand.id,
            "made_item_id": lot.made_item_id,
            "made_item_source_assignment": "skipped_disabled",
        }

        saved_lot = await self.lot_repo.get_by_id(lot.id)
        assert any("approved" in c.lower() for c in saved_lot.changes)
        assert any(f"#{demand.id}" in c for c in saved_lot.changes)
        assert self.uow.committed is True

    async def test_approves_a_rejected_lot_clearing_rejection_fields(self):
        lot = await self.lot_repo.save(
            make_lot(
                source_approval_status=SourceApprovalStatus.REJECTED,
                source_rejected_by_id=2,
                source_rejected_date=datetime(2026, 1, 2, tzinfo=UTC),
                source_rejection_reason="Wrong dimension.",
            )
        )
        result = await self._use_case().execute(self.actor, lot.id)

        assert result.source_approval_status == SourceApprovalStatus.APPROVED.value
        assert result.source_approved_by_id == self.actor.id
        assert result.source_rejected_by_id is None
        assert result.source_rejected_date is None
        assert result.source_rejection_reason is None

    @pytest.mark.parametrize(
        "status",
        [SourceApprovalStatus.NOT_REQUIRED, SourceApprovalStatus.APPROVED],
    )
    async def test_rejects_a_non_decidable_status(self, status):
        lot = await self.lot_repo.save(make_lot(source_approval_status=status))
        with pytest.raises(SourceApprovalNotPendingError):
            await self._use_case().execute(self.actor, lot.id)
        assert len(self.demand_repo.demands) == 0

    async def test_rejects_when_a_demand_is_already_linked_even_if_pending(self):
        # Race backstop (approve_lot_source.py docstring): the status guard
        # alone leaves a window for two simultaneous approvers.
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING, input_demand_id=99)
        )
        with pytest.raises(LotRawMaterialAlreadyLinkedError):
            await self._use_case().execute(self.actor, lot.id)
        assert len(self.demand_repo.demands) == 0

    async def test_write_lots_without_manage_lots_is_insufficient(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        with pytest.raises(InsufficientPermissionsError):
            await self._use_case().execute(actor, lot.id)

    @pytest.mark.parametrize("terminal_status", [LotStatus.COMPLETED, LotStatus.CANCELED])
    async def test_terminal_lot_is_locked_even_for_an_approver(self, terminal_status):
        lot = await self.lot_repo.save(
            make_lot(status=terminal_status, source_approval_status=SourceApprovalStatus.PENDING)
        )
        with pytest.raises(LotStructureLockedError):
            await self._use_case().execute(self.actor, lot.id)

    async def test_permission_error_takes_precedence_over_terminal_status(self):
        # LotRules.assert_can_approve_source checks permission BEFORE
        # status, so a permission-less caller gets 403, not 409, even on a
        # lot that would also fail the terminal-status check.
        lot = await self.lot_repo.save(
            make_lot(
                status=LotStatus.COMPLETED,
                source_approval_status=SourceApprovalStatus.PENDING,
            )
        )
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self._use_case().execute(actor, lot.id)

    async def test_recompute_is_called_exactly_once_on_success(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        recompute = FakeRecomputeSchedule()
        await self._use_case(recompute).execute(self.actor, lot.id)
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        recompute = FailingRecomputeSchedule()
        result = await self._use_case(recompute).execute(self.actor, lot.id)
        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert result.source_approval_status == SourceApprovalStatus.APPROVED.value
        assert result.input_demand_id is not None

    async def test_a_stale_edit_version_is_refused_without_a_demand(self):
        lot = make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        lot.edit_version = 3
        lot = await self.lot_repo.save(lot)
        with pytest.raises(ConcurrentModificationError):
            await self._use_case().execute(self.actor, lot.id, expected_edit_version=2)
        assert len(self.demand_repo.demands) == 0
        assert (await self.lot_repo.get_by_id(lot.id)).source_approval_status == "pending"

    async def test_an_approval_moves_the_edit_version(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        result = await self._use_case().execute(self.actor, lot.id, expected_edit_version=0)
        assert result.edit_version == 1

    @pytest.mark.parametrize("status", [ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED])
    async def test_a_project_that_is_not_active_is_refused(self, status):
        project = make_project(id=1)
        project.status = status
        self.project_repo = ActiveProjectRepository([project])
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        with pytest.raises(ProjectInactiveError):
            await self._use_case().execute(self.actor, lot.id)
        assert len(self.demand_repo.demands) == 0

    @pytest.mark.parametrize(
        "status", [SourceItemCatalogueStatus.INACTIVE, SourceItemCatalogueStatus.REPLACED]
    )
    async def test_a_source_item_new_work_may_not_name_is_refused(self, status):
        self.source_item_repo = FakeSourceItemRepository([make_source_item(id=1, status=status)])
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        with pytest.raises(SourceItemInactiveError, match="switch the source first"):
            await self._use_case().execute(self.actor, lot.id)
        assert len(self.demand_repo.demands) == 0


# ── RejectLotSource ──────────────────────────────────────────────────


class TestRejectLotSource:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.MANAGE_LOTS])

    def _use_case(self) -> RejectLotSource:
        return RejectLotSource(lot_repo=self.lot_repo, uow=self.uow)

    async def test_rejects_a_pending_lot(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        result = await self._use_case().execute(
            self.actor, lot.id, RejectLotSourceCommand(reason="Wrong dimension.")
        )

        assert result.source_approval_status == SourceApprovalStatus.REJECTED.value
        assert result.source_rejected_by_id == self.actor.id
        assert result.source_rejected_date is not None
        assert result.source_rejection_reason == "Wrong dimension."
        assert result.source_approved_by_id is None
        assert result.source_approved_date is None
        # No demand: RejectLotSource never touches a demand repository.
        assert result.input_demand_id is None

        events = await self.lot_repo.get_events(lot.id)
        assert len(events) == 1
        assert events[0].event_type == LotEventType.LOT_SOURCE_REJECTED
        assert self.uow.committed is True

    @pytest.mark.parametrize(
        "status",
        [
            SourceApprovalStatus.REJECTED,
            SourceApprovalStatus.APPROVED,
            SourceApprovalStatus.NOT_REQUIRED,
        ],
    )
    async def test_rejects_a_non_pending_status(self, status):
        lot = await self.lot_repo.save(make_lot(source_approval_status=status))
        with pytest.raises(SourceApprovalNotPendingError):
            await self._use_case().execute(self.actor, lot.id, RejectLotSourceCommand(reason="No."))

    async def test_write_lots_without_manage_lots_is_insufficient(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        with pytest.raises(InsufficientPermissionsError):
            await self._use_case().execute(actor, lot.id, RejectLotSourceCommand(reason="No."))

    @pytest.mark.parametrize("terminal_status", [LotStatus.COMPLETED, LotStatus.CANCELED])
    async def test_terminal_lot_is_locked_even_for_an_approver(self, terminal_status):
        lot = await self.lot_repo.save(
            make_lot(status=terminal_status, source_approval_status=SourceApprovalStatus.PENDING)
        )
        with pytest.raises(LotStructureLockedError):
            await self._use_case().execute(self.actor, lot.id, RejectLotSourceCommand(reason="No."))

    async def test_permission_error_takes_precedence_over_terminal_status(self):
        lot = await self.lot_repo.save(
            make_lot(
                status=LotStatus.COMPLETED,
                source_approval_status=SourceApprovalStatus.PENDING,
            )
        )
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self._use_case().execute(actor, lot.id, RejectLotSourceCommand(reason="No."))

    async def test_a_stale_edit_version_is_refused(self):
        lot = make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        lot.edit_version = 3
        lot = await self.lot_repo.save(lot)
        with pytest.raises(ConcurrentModificationError):
            await self._use_case().execute(
                self.actor, lot.id, RejectLotSourceCommand(reason="No.", expected_edit_version=2)
            )
        assert (await self.lot_repo.get_by_id(lot.id)).source_approval_status == "pending"

    async def test_a_rejection_moves_the_edit_version(self):
        lot = await self.lot_repo.save(
            make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        )
        result = await self._use_case().execute(
            self.actor, lot.id, RejectLotSourceCommand(reason="No.", expected_edit_version=0)
        )
        assert result.edit_version == 1


# ── CreateLot ────────────────────────────────────────────────────────


class TestCreateLotSourceApproval:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.order_repo = FakeProductionOrderRepository()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _use_case(self, made_item, settings_repo) -> CreateLot:
        return CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=FakeMadeItemRepository([made_item]),
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            settings_repo=settings_repo,
            source_item_demand_repo=self.source_item_demand_repo,
            order_repo=self.order_repo,
            inspection_method_repo=self.inspection_method_repo,
            machine_repo=self.machine_repo,
            uow=self.uow,
            event_bus=self.bus,
            reconciler=lot_reconciler(self.lot_repo, self.order_repo),
        )

    async def test_setting_on_a_source_item_source_creates_a_pending_lot_with_no_demand(self):
        made_item = make_made_item(processes=[], source_item_id=9)
        use_case = self._use_case(
            made_item, ApprovalSettingsRepo(require_source_item_approval=True)
        )
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert result.source_approval_status == SourceApprovalStatus.PENDING.value
        assert result.input_demand_id is None
        assert len(self.source_item_demand_repo.demands) == 0

    async def test_setting_off_a_source_item_source_creates_demand_as_before(self):
        made_item = make_made_item(processes=[], source_item_id=9)
        use_case = self._use_case(
            made_item, ApprovalSettingsRepo(require_source_item_approval=False)
        )
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert result.source_approval_status == SourceApprovalStatus.NOT_REQUIRED.value
        assert result.input_demand_id is not None

    async def test_setting_on_a_bought_item_source_is_never_gated(self):
        made_item = make_made_item(processes=[], bought_item_id=7)
        use_case = self._use_case(
            made_item, ApprovalSettingsRepo(require_source_item_approval=True)
        )
        result = await use_case.execute(
            self.actor, CreateLotCommand(made_item_id=1, project_id=1, quantity=5.0)
        )

        assert result.source_approval_status == SourceApprovalStatus.NOT_REQUIRED.value
        assert result.input_demand_id is not None

    async def test_setting_on_an_alteration_lot_is_never_gated(self):
        made_item = make_made_item(processes=[], source_item_id=9)
        self.demand_repo = FakeMadeItemDemandRepository(
            [make_demand(id=1, quantity=5.0, is_alteration=True, alteration_of_made_item_id=99)]
        )
        use_case = self._use_case(
            made_item, ApprovalSettingsRepo(require_source_item_approval=True)
        )
        result = await use_case.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=5.0,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=5.0)],
            ),
        )

        assert result.source_approval_status == SourceApprovalStatus.NOT_REQUIRED.value
        assert result.input_demand_id is None


# ── SwitchLotMaterialSource ──────────────────────────────────────────


class TestSwitchLotMaterialSourceApproval:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.bought_item_repo = FakeBoughtItemRepository([make_bought_item(id=1)])
        self.source_item_repo = FakeSourceItemRepository([make_source_item(id=1)])
        self.made_item_repo = FakeMadeItemRepository([make_made_item(id=1)])
        self.demand_repo = FakeSourceItemDemandRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _use_case(self, settings_repo) -> SwitchLotMaterialSource:
        return SwitchLotMaterialSource(
            lot_repo=self.lot_repo,
            bought_item_repo=self.bought_item_repo,
            source_item_repo=self.source_item_repo,
            made_item_repo=self.made_item_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=(allocations := FakeSourceItemAllocationRepository()),
            settings_repo=settings_repo,
            project_repo=ActiveProjectRepository(),
            line_release=fake_line_release(allocations),
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

    async def test_switch_to_source_item_with_setting_on_resets_to_pending_and_clears_decisions(
        self,
    ):
        # Start from an already-APPROVED lot to prove every decision field
        # gets reset, not just the status.
        lot = await self._make_lot(
            source_approval_status=SourceApprovalStatus.APPROVED,
            source_approved_by_id=42,
            source_approved_date=datetime(2026, 1, 2, tzinfo=UTC),
        )
        use_case = self._use_case(ApprovalSettingsRepo(require_source_item_approval=True))
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(source_item_id=1)
        )

        assert result.source_approval_status == SourceApprovalStatus.PENDING.value
        assert result.source_approved_by_id is None
        assert result.source_approved_date is None
        assert result.source_rejected_by_id is None
        assert result.source_rejected_date is None
        assert result.source_rejection_reason is None
        assert result.input_demand_id is None
        assert len(self.demand_repo.demands) == 0

    async def test_switch_to_bought_item_with_setting_on_creates_demand_immediately(self):
        lot = await self._make_lot()
        use_case = self._use_case(ApprovalSettingsRepo(require_source_item_approval=True))
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
        )

        assert result.source_approval_status == SourceApprovalStatus.NOT_REQUIRED.value
        assert result.input_demand_id is not None

    async def test_switch_to_source_item_with_setting_off_creates_demand_immediately(self):
        lot = await self._make_lot()
        use_case = self._use_case(ApprovalSettingsRepo(require_source_item_approval=False))
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(source_item_id=1)
        )

        assert result.source_approval_status == SourceApprovalStatus.NOT_REQUIRED.value
        assert result.input_demand_id is not None

    async def test_a_switch_moves_the_edit_version_so_a_stale_decision_is_refused(self):
        lot = await self._make_lot(source_approval_status=SourceApprovalStatus.PENDING)
        use_case = self._use_case(ApprovalSettingsRepo(require_source_item_approval=True))
        result = await use_case.execute(
            self.actor, lot.id, SwitchLotMaterialSourceCommand(source_item_id=1)
        )
        assert result.edit_version == 1

        approve = ApproveLotSource(
            lot_repo=self.lot_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
            project_repo=ActiveProjectRepository(),
            source_item_repo=self.source_item_repo,
        )
        approver = make_user(permissions=[Permission.MANAGE_LOTS])
        with pytest.raises(ConcurrentModificationError):
            await approve.execute(approver, lot.id, expected_edit_version=0)
        assert len(self.demand_repo.demands) == 0

    @pytest.mark.parametrize(
        "status", [LotStatus.COMPLETED, LotStatus.CANCELED, LotStatus.SCRAPPED]
    )
    async def test_a_terminal_lot_is_refused_for_a_manager_too(self, status):
        lot = await self._make_lot(status=status)
        manager = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
        use_case = self._use_case(ApprovalSettingsRepo(require_source_item_approval=False))
        with pytest.raises(LotStructureLockedError):
            await use_case.execute(
                manager, lot.id, SwitchLotMaterialSourceCommand(bought_item_id=1)
            )
        assert len(self.demand_repo.demands) == 0


class TestApprovalAfterSwitchingAnOrderedSource:
    """A lot that switches away from an already ordered source keeps what
    arrived, and the new source is demanded for the rest only. With source
    approval on the switch creates no demand, and the approval must demand
    that same rest rather than the whole lot."""

    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.source_item_repo = FakeSourceItemRepository(
            [make_source_item(id=1), make_source_item(id=2)]
        )
        self.old_demand = make_source_item_demand(
            id=50, lot_id=1, status=SourceItemDemandStatus.ORDERED
        )
        self.demand_repo = FakeSourceItemDemandRepository([self.old_demand])
        line = make_order_item(id=1, line_type=OrderLineType.SOURCE)
        line.status = OrderItemStatus.PARTIALLY_DELIVERED
        line.quantity = 5.0
        line.quantity_delivered = 2.0
        self.order_items = FakeOrderItemRepository([line])
        self.allocations = FakeSourceItemAllocationRepository(
            [SourceItemDemandAllocation(demand_item_id=50, order_item_id=1, quantity=5.0)]
        )
        self.uow = FakeUnitOfWork()

    async def _switched_lot(self, require_approval: bool) -> ProductionLot:
        lot = await self.lot_repo.save(
            make_lot(
                id=1,
                quantity=5.0,
                source_item_id=1,
                input_demand_id=50,
                source_approval_status=SourceApprovalStatus.APPROVED,
            )
        )
        switch = SwitchLotMaterialSource(
            lot_repo=self.lot_repo,
            bought_item_repo=FakeBoughtItemRepository([]),
            source_item_repo=self.source_item_repo,
            made_item_repo=FakeMadeItemRepository([]),
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=self.allocations,
            settings_repo=ApprovalSettingsRepo(require_source_item_approval=require_approval),
            project_repo=ActiveProjectRepository(),
            line_release=fake_line_release(self.allocations, self.order_items),
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
        )
        await switch.execute(
            make_user(permissions=[Permission.WRITE_LOTS]),
            lot.id,
            SwitchLotMaterialSourceCommand(source_item_id=2, confirm_replace_demand=True),
        )
        switched = await self.lot_repo.get_by_id(lot.id)
        assert switched is not None
        return switched

    async def test_without_approval_the_switch_demands_the_missing_rest(self):
        lot = await self._switched_lot(require_approval=False)

        assert lot.input_demand_id not in (None, 50)
        demand = await self.demand_repo.get_by_id(lot.input_demand_id)
        assert demand is not None and demand.quantity == 3.0

    async def test_the_approval_demands_the_missing_rest_not_the_whole_lot(self):
        lot = await self._switched_lot(require_approval=True)
        assert lot.source_approval_status == SourceApprovalStatus.PENDING
        assert lot.input_demand_id is None

        approve = ApproveLotSource(
            lot_repo=self.lot_repo,
            source_item_demand_repo=self.demand_repo,
            source_item_allocation_repo=self.allocations,
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
            project_repo=ActiveProjectRepository(),
            source_item_repo=self.source_item_repo,
        )
        result = await approve.execute(make_user(permissions=[Permission.MANAGE_LOTS]), lot.id)

        demand = await self.demand_repo.get_by_id(result.input_demand_id)
        assert demand is not None
        assert (demand.quantity, demand.unit, demand.items_per_unit) == (3.0, "pcs", 1.0)


# ── CreateSourceItemDemand (manual "Demand Source Item") ────────────


class TestCreateSourceItemDemandApprovalGate:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.lot = await self.lot_repo.save(
            make_lot(source_item_id=1, source_approval_status=SourceApprovalStatus.NOT_REQUIRED)
        )
        self.demand_repo = FakeSourceItemDemandRepository()
        self.project_repo = FakeProjectRepository([make_project(id=1)])
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _use_case(self) -> CreateSourceItemDemand:
        return CreateSourceItemDemand(
            self.lot_repo,
            self.demand_repo,
            self.project_repo,
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
        )

    def _cmd(self, **kwargs) -> CreateSourceItemDemandCommand:
        defaults = dict(lot_id=self.lot.id, quantity=5.0)
        defaults.update(kwargs)
        return CreateSourceItemDemandCommand(**defaults)

    async def test_pending_lot_raises(self):
        self.lot.source_approval_status = SourceApprovalStatus.PENDING
        with pytest.raises(SourceItemApprovalRequiredError):
            await self._use_case().execute(self.actor, self._cmd())

    async def test_rejected_lot_raises(self):
        self.lot.source_approval_status = SourceApprovalStatus.REJECTED
        with pytest.raises(SourceItemApprovalRequiredError):
            await self._use_case().execute(self.actor, self._cmd())

    async def test_approved_lot_with_no_linked_demand_succeeds(self):
        # "Approval survives a demand cancel": an approved lot whose
        # demand was canceled clears input_demand_id
        # but keeps status == approved, so it can be re-demanded without a
        # second approval.
        self.lot.source_approval_status = SourceApprovalStatus.APPROVED
        self.lot.input_demand_id = None
        result = await self._use_case().execute(self.actor, self._cmd())

        assert result.status == SourceItemDemandStatus.OPEN.value
        assert (await self.lot_repo.get_by_id(self.lot.id)).input_demand_id == result.id


# ── UpdateProductionSettings backfill ───────────────────────────────


class _RecordingLotRepoForBackfill:
    """Minimal IProductionLotRepository double: only the one method
    UpdateProductionSettings' backfill calls, recording the call into a
    shared log so its position relative to save_production can be
    asserted."""

    def __init__(self, call_log: list[str], return_count: int = 3) -> None:
        self._log = call_log
        self._return_count = return_count
        self.enabled_calls: list[bool] = []

    async def reset_source_approval_for_setting_change(self, enabled: bool) -> int:
        self.enabled_calls.append(enabled)
        self._log.append(f"backfill:{enabled}")
        return self._return_count


class _OrderTrackingAdminSettingsRepository(SettingsRepoFake):
    """SettingsRepoFake (tests/unit/admin_settings/fakes.py) predates the
    backfill ordering requirement. This subclass logs save_production
    calls into the same shared list a _RecordingLotRepoForBackfill call is
    logged into, so a test can prove the backfill runs BEFORE the settings
    save rather than merely that both happen."""

    def __init__(self, call_log: list[str], require_source_item_approval: bool = False) -> None:
        super().__init__()
        self._log = call_log
        self.production.require_source_item_approval = require_source_item_approval

    async def save_production(self, settings):
        self._log.append("save_production")
        return await super().save_production(settings)


class TestUpdateProductionSettingsSourceApprovalBackfill:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.inspection_method_repo = SettingsInspectionMethodFake()

    async def test_flip_off_to_on_backfills_enabled_true_before_the_save(self):
        call_log: list[str] = []
        repo = _OrderTrackingAdminSettingsRepository(call_log, require_source_item_approval=False)
        lot_repo = _RecordingLotRepoForBackfill(call_log)
        uow = FakeUnitOfWork()
        use_case = UpdateProductionSettings(repo, self.inspection_method_repo, lot_repo, uow=uow)

        result = await use_case.execute(
            self.actor, UpdateProductionSettingsCommand(require_source_item_approval=True)
        )

        assert result.require_source_item_approval is True
        assert lot_repo.enabled_calls == [True]
        assert call_log == ["backfill:True", "save_production"]
        assert uow.committed is True

    async def test_flip_on_to_off_backfills_enabled_false(self):
        call_log: list[str] = []
        repo = _OrderTrackingAdminSettingsRepository(call_log, require_source_item_approval=True)
        lot_repo = _RecordingLotRepoForBackfill(call_log)
        use_case = UpdateProductionSettings(
            repo, self.inspection_method_repo, lot_repo, uow=FakeUnitOfWork()
        )

        result = await use_case.execute(
            self.actor, UpdateProductionSettingsCommand(require_source_item_approval=False)
        )

        assert result.require_source_item_approval is False
        assert lot_repo.enabled_calls == [False]
        assert call_log == ["backfill:False", "save_production"]

    async def test_unchanged_flag_does_not_call_the_backfill(self):
        call_log: list[str] = []
        repo = _OrderTrackingAdminSettingsRepository(call_log, require_source_item_approval=False)
        lot_repo = _RecordingLotRepoForBackfill(call_log)
        use_case = UpdateProductionSettings(
            repo, self.inspection_method_repo, lot_repo, uow=FakeUnitOfWork()
        )

        await use_case.execute(self.actor, UpdateProductionSettingsCommand(response_time_days=3))

        assert lot_repo.enabled_calls == []
        assert call_log == ["save_production"]
