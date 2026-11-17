"""
A project with live work is not deleted: the refusal counts that work and
nothing is canceled on the project's behalf. A deleted project takes no new
allocations through auto-allocate. No database, no HTTP.
"""

import pytest

from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.auto_allocate import (
    AutoAllocate,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.auto_allocate import (
    AutoAllocateSourceItemDemand,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.application.use_cases.project.delete_project import DeleteProject
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectDeleteBlockedError
from src.modules.workspace.domain.events.project_events import ProjectDeleted
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from tests.factories import make_user
from tests.unit import test_bought_item_allocation_use_cases as bought
from tests.unit import test_source_item_allocation_use_cases as source
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.test_project_use_cases import make_project


class _Projects:
    """A project repository that reports a fixed amount of live work and
    does not find a deleted project."""

    def __init__(self, projects: list[Project], live_work: ProjectLiveWork | None = None) -> None:
        self._projects = {p.id: p for p in projects}
        self._live_work = live_work or ProjectLiveWork()
        self.saved: list[Project] = []

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        return None

    async def get_by_id(self, id: int) -> Project | None:
        project = self._projects.get(id)
        return project if project is not None and not project.deleted else None

    async def get_live_work(self, project_id: int) -> ProjectLiveWork:
        return self._live_work

    async def save(self, project: Project) -> Project:
        self.saved.append(project)
        return project


class TestDeleteProject:
    def setup_method(self) -> None:
        self.manager = make_user(
            id=1, permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]
        )
        self.project = make_project(id=1, project_number="P-0815")
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()

    def _use_case(self, live_work: ProjectLiveWork) -> tuple[DeleteProject, _Projects]:
        projects = _Projects([self.project], live_work)
        return DeleteProject(projects, event_bus=self.bus, uow=self.uow, work=projects), projects

    async def test_a_project_with_live_work_is_refused_with_the_counts(self):
        use_case, projects = self._use_case(
            ProjectLiveWork(lots=2, production_orders=1, order_lines=1, made_demands=3)
        )

        with pytest.raises(ProjectDeleteBlockedError) as refused:
            await use_case.execute(actor=self.manager, project_id=1)

        message = str(refused.value)
        assert "P-0815" in message
        assert "2 lots, 1 production order, 1 order line, 3 made item demands" in message
        assert self.project.deleted is False
        assert self.project.status == "active"
        assert projects.saved == []
        assert self.bus.published == []
        assert not self.uow.committed

    async def test_a_project_without_live_work_is_deleted(self):
        use_case, _ = self._use_case(ProjectLiveWork())

        result = await use_case.execute(actor=self.manager, project_id=1)

        assert result.deleted is True
        assert result.status == "archived"
        (event,) = self.bus.published
        assert isinstance(event, ProjectDeleted)
        assert self.uow.committed


# ── Auto-allocate skips a deleted project ────────────────────────────────


async def test_bought_auto_allocate_gives_a_deleted_project_nothing():
    demand = bought.make_demand(id=1, quantity=10.0, item_id=1)
    demand_repo = bought.FakeDemandRepository([demand])
    allocations = bought.FakeAllocationRepository()
    use_case = AutoAllocate(
        demand_repo,
        bought.FakeOrderItemRepository([bought.make_order_item(id=1, quantity=6.0)]),
        allocations,
        uow=FakeUnitOfWork(),
        project_repo=_Projects([make_project(id=1, deleted=True)]),
        reconciler=demand_reconciler(
            bought_demands=demand_repo,
            order_items=bought.FakeOrderItemRepository(
                [bought.make_order_item(id=1, quantity=6.0)]
            ),
            bought_allocations=allocations,
        ),
        fill_repos=LineFillRepos(bought=allocations, source=FakeSourceItemAllocationRepository()),
    )
    actor = bought.make_user(permissions=[Permission.WRITE_ALLOCATIONS])

    result = await use_case.execute(actor=actor, cmd=AutoAllocateCommand(demand_item_id=1))

    assert result.allocations_created == 0
    assert result.remaining_unallocated == 10.0
    assert await allocations.get_by_demand_item_id(1) == []
    assert (await demand_repo.get_by_id(1)).status == "open"


async def test_bought_auto_allocate_still_serves_a_live_project():
    demand_repo = bought.FakeDemandRepository([bought.make_demand(id=1, quantity=10.0)])
    use_case = AutoAllocate(
        demand_repo,
        bought.FakeOrderItemRepository([bought.make_order_item(id=1, quantity=6.0)]),
        bought.FakeAllocationRepository(),
        uow=FakeUnitOfWork(),
        project_repo=_Projects([make_project(id=1)]),
        reconciler=demand_reconciler(
            bought_demands=demand_repo,
            order_items=bought.FakeOrderItemRepository(
                [bought.make_order_item(id=1, quantity=6.0)]
            ),
            bought_allocations=bought.FakeAllocationRepository(),
        ),
        fill_repos=LineFillRepos(
            bought=bought.FakeAllocationRepository(), source=FakeSourceItemAllocationRepository()
        ),
    )
    actor = bought.make_user(permissions=[Permission.WRITE_ALLOCATIONS])

    result = await use_case.execute(actor=actor, cmd=AutoAllocateCommand(demand_item_id=1))

    assert result.total_newly_allocated == 6.0


async def test_source_auto_allocate_gives_a_deleted_project_nothing():
    demand_repo = source.FakeDemandRepository([source.make_demand(id=1, quantity=10.0)])
    allocations = source.FakeAllocationRepository()
    use_case = AutoAllocateSourceItemDemand(
        demand_repo,
        source.FakeOrderItemRepository([source.make_order_item(id=1, quantity=6.0)]),
        allocations,
        uow=FakeUnitOfWork(),
        project_repo=_Projects([]),
        reconciler=demand_reconciler(
            source_demands=demand_repo,
            order_items=source.FakeOrderItemRepository(
                [source.make_order_item(id=1, quantity=6.0)]
            ),
            source_allocations=allocations,
        ),
        fill_repos=LineFillRepos(bought=FakeBoughtItemAllocationRepository(), source=allocations),
    )
    actor = source.make_user(permissions=[Permission.WRITE_ALLOCATIONS])

    result = await use_case.execute(
        actor=actor, cmd=AutoAllocateSourceItemDemandCommand(demand_item_id=1)
    )

    assert result.allocations_created == 0
    assert result.remaining_unallocated == 10.0
    assert await allocations.get_by_demand_item_id(1) == []
