"""
A lot a user creates needs an active project and a made item new work may
name; a lot a disposition spawns continues existing work and is exempt.
Auto-assign leaves out the demands lot creation would refuse, so one of them
cannot undo the whole sweep. No database, no HTTP.
"""

from dataclasses import replace

import pytest

from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.auto_assign_lots import (
    AutoAssignLots,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectInactiveError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
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
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.test_project_use_cases import make_project


class _Projects:
    """The projects a lot may name; a deleted project is not found."""

    def __init__(self, projects: list[Project]) -> None:
        self._projects = {p.id: p for p in projects if not p.deleted}

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        return None

    async def get_by_id(self, id: int) -> Project | None:
        return self._projects.get(id)


class _Setup:
    def setup_method(self) -> None:
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])
        self.projects = _Projects([make_project(id=1)])
        self.orders = FakeProductionOrderRepository()
        self.reconciler = lot_reconciler(self.lot_repo, self.orders)

    def _create_lot(self, *made_items) -> CreateLot:
        return CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=FakeMadeItemRepository(list(made_items)),
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            settings_repo=FakeAdminSettingsRepository(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            order_repo=self.orders,
            inspection_method_repo=FakeInspectionMethodRepository(),
            machine_repo=FakeProductionMachineRepository(),
            uow=self.uow,
            event_bus=FakeEventBus(),
            reconciler=self.reconciler,
            project_repo=self.projects,
        )


class TestCreateLotGuards(_Setup):
    @staticmethod
    def _cmd(project_id: int = 1) -> CreateLotCommand:
        return CreateLotCommand(made_item_id=1, project_id=project_id, quantity=5.0)

    @pytest.mark.parametrize(
        ("changes", "reason"),
        [
            ({"status": MadeItemCatalogueStatus.REPLACED}, "is replaced"),
            ({"archived": True}, "is archived"),
            ({"pdm_sync_state": PdmSyncState.MISSING}, "is missing in PDM"),
        ],
    )
    async def test_a_made_item_new_work_may_not_name_gets_no_new_lot(self, changes, reason):
        made_item = replace(make_made_item(processes=[]), **changes)

        with pytest.raises(MadeItemInactiveError, match=reason):
            await self._create_lot(made_item).execute(self.actor, self._cmd())

        assert not self.uow.committed

    async def test_a_project_on_hold_gets_no_new_lot(self):
        self.projects = _Projects([make_project(id=1, status=ProjectStatus.ON_HOLD)])

        with pytest.raises(ProjectInactiveError, match="on hold"):
            await self._create_lot(make_made_item(processes=[])).execute(self.actor, self._cmd())

    async def test_a_deleted_project_is_not_found(self):
        self.projects = _Projects([make_project(id=1, deleted=True)])

        with pytest.raises(ProjectNotFoundError):
            await self._create_lot(make_made_item(processes=[])).execute(self.actor, self._cmd())

    async def test_an_active_project_and_item_get_the_lot(self):
        result = await self._create_lot(make_made_item(processes=[])).execute(
            self.actor, self._cmd()
        )

        assert result.project_id == 1

    async def test_a_lot_a_disposition_spawns_continues_existing_work_unchecked(self):
        self.projects = _Projects([make_project(id=1, status=ProjectStatus.COMPLETED)])
        made_item = replace(make_made_item(processes=[]), status=MadeItemCatalogueStatus.REPLACED)

        lot = await self._create_lot(made_item).create_no_commit(
            self.actor, self._cmd(), check_create_permission=False
        )

        assert lot.made_item_id == 1


class TestAutoAssignLeavesOutWhatLotCreationRefuses(_Setup):
    def _use_case(self, *made_items) -> AutoAssignLots:
        return AutoAssignLots(
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            lot_repo=self.lot_repo,
            create_lot=self._create_lot(*made_items),
            uow=self.uow,
            event_bus=FakeEventBus(),
            reconciler=self.reconciler,
            project_repo=self.projects,
        )

    def _seed(self) -> tuple:
        active = make_made_item(id=1, processes=[])
        replaced = replace(
            make_made_item(id=2, processes=[]), status=MadeItemCatalogueStatus.REPLACED
        )
        self.projects = _Projects(
            [
                make_project(id=1),
                make_project(id=2, status=ProjectStatus.ON_HOLD),
                make_project(id=3, deleted=True),
            ]
        )
        demands = [
            replace(make_demand(id=1, quantity=3.0, made_item_id=1, project_id=1), item=active),
            replace(make_demand(id=2, quantity=2.0, made_item_id=1, project_id=2), item=active),
            replace(make_demand(id=3, quantity=4.0, made_item_id=1, project_id=3), item=active),
            replace(make_demand(id=4, quantity=1.0, made_item_id=2, project_id=1), item=replaced),
        ]
        self.demand_repo = FakeMadeItemDemandRepository(demands)
        return active, replaced

    async def test_only_demands_of_active_projects_with_a_demandable_item_are_grouped(self):
        use_case = self._use_case(*self._seed())

        groups = await use_case.preview(self.actor)

        assert [(g.project_id, g.made_item_id) for g in groups] == [(1, 1)]
        assert [d.demand_item_id for d in groups[0].demands] == [1]

    async def test_the_sweep_creates_the_lots_the_preview_showed(self):
        use_case = self._use_case(*self._seed())

        lots = await use_case.execute(self.actor)

        assert [(lot.project_id, lot.made_item_id, lot.quantity) for lot in lots] == [(1, 1, 3.0)]
        assert self.uow.commits == 1
