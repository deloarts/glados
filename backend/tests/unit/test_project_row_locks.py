"""
A project delete locks the project row before it counts the project's live
work, and a use case that creates work for a project locks the project in
shared mode before it checks that the project is active, so a delete either
counts the new work or the creation finds the project gone. One log records
the locks and the reads of the project. No database, no HTTP.
"""

from typing import Any

from src.modules.fulfillment.application.dto.bought_item_demand_dto import CreateDemandItemCommand
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_demand_item import (
    CreateDemandItem,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.application.use_cases.project.delete_project import DeleteProject
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.test_demand_item_use_cases import FakeBoughtItemRepository
from tests.unit.test_demand_item_use_cases import FakeDemandRepository
from tests.unit.test_demand_item_use_cases import make_bought_item
from tests.unit.test_demand_item_use_cases import make_project


class _LoggedProjects:
    """A project repository that logs its locks and reads."""

    def __init__(self, project: Project) -> None:
        self._project = project
        self.log: list[tuple[str, Any]] = []

    async def lock_for_update(self, id: int) -> None:
        self.log.append(("lock for update", id))

    async def lock_for_share(self, ids: list[int]) -> None:
        self.log.append(("lock for share", tuple(ids)))

    async def get_by_id(self, id: int) -> Project | None:
        self.log.append(("read", id))
        return self._project if id == self._project.id else None

    async def get_live_work(self, project_id: int) -> ProjectLiveWork:
        self.log.append(("count live work", project_id))
        return ProjectLiveWork()

    async def save(self, project: Project) -> Project:
        self.log.append(("save", project.id))
        return project


async def test_a_delete_locks_the_project_before_it_counts_the_live_work() -> None:
    projects = _LoggedProjects(make_project(id=1))

    await DeleteProject(
        projects, event_bus=FakeEventBus(), uow=FakeUnitOfWork(), work=projects
    ).execute(make_user(permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]), 1)

    assert projects.log == [
        ("lock for update", 1),
        ("read", 1),
        ("count live work", 1),
        ("save", 1),
    ]


async def test_a_demand_creation_locks_the_project_in_shared_mode_before_checking_it() -> None:
    projects = _LoggedProjects(make_project(id=1))
    demands = FakeDemandRepository()

    await CreateDemandItem(
        demands,
        FakeBoughtItemRepository([make_bought_item(id=1)]),
        projects,
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
        reconciler=demand_reconciler(bought_demands=demands),
    ).execute(
        make_user(permissions=[Permission.WRITE_DEMAND_ITEMS]),
        CreateDemandItemCommand(item_id=1, project_id=1, quantity=5.0, unit="pcs"),
    )

    assert projects.log[:2] == [("lock for share", (1,)), ("read", 1)]
