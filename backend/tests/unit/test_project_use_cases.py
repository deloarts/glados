"""
Unit tests for all project use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.services.project_work_propagation import (
    ProjectWorkPropagation,
)
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.application.dto.project_dto import CreateProjectCommand
from src.modules.workspace.application.dto.project_dto import UpdateProjectCommand
from src.modules.workspace.application.use_cases.project.create_project import CreateProject
from src.modules.workspace.application.use_cases.project.delete_project import DeleteProject
from src.modules.workspace.application.use_cases.project.get_project import GetMyProjects
from src.modules.workspace.application.use_cases.project.get_project import GetProject
from src.modules.workspace.application.use_cases.project.get_project import GetProjectByNumber
from src.modules.workspace.application.use_cases.project.get_project import GetProjects
from src.modules.workspace.application.use_cases.project.update_project import UpdateProject
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectAlreadyExistsError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.errors import ProjectNumberPatternError
from src.modules.workspace.domain.errors import ProjectProductRequiredError
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto
from tests.factories import make_user
from tests.unit.production_order.fakes import FakeLockPlan
from tests.unit.production_order.fakes import FakeProductionOrderRepository

# ── Helpers ───────────────────────────────────────────────────────────


def make_project(
    id: int = 1,
    project_number: str = "P-001",
    designated_user_id: int = 1,
    status: ProjectStatus = ProjectStatus.ACTIVE,
    deleted: bool = False,
    required_delivery_date_made: date | None = None,
    required_delivery_date_bought: date | None = None,
    changes: list[str] | None = None,
) -> Project:
    return Project(
        id=id,
        project_number=project_number,
        description="Test project",
        status=status,
        designated_user_id=designated_user_id,
        created=datetime.now(UTC),
        deleted=deleted,
        required_delivery_date_made=required_delivery_date_made,
        required_delivery_date_bought=required_delivery_date_bought,
        changes=list(changes) if changes else [],
    )


def diff_entry(changes: list[str]) -> str:
    """The UpdateProject field-diff entry, located by content rather than by
    position: a project's history may also carry a leading creation entry and
    a trailing propagation summary, so neither [0] nor [-1] is reliable."""
    return next(c for c in changes if "Item updated:" in c or "No changes." in c)


class FakeProjectRepository:
    def __init__(self, projects: list[Project] | None = None):
        self._projects: dict[int, Project] = {}
        self._next_id = 1
        for p in projects or []:
            self._projects[p.id] = p
            self._next_id = max(self._next_id, p.id + 1)

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        return None

    async def get_by_id(self, id: int):
        return self._projects.get(id)

    async def get_by_project_number(self, number: str):
        return next((p for p in self._projects.values() if p.project_number == number), None)

    async def get_by_designated_user_id(self, user_id: int):
        return [p for p in self._projects.values() if p.designated_user_id == user_id]

    async def get_multi(self, filters: ProjectFilterDto):
        projects = [p for p in self._projects.values() if not p.deleted]
        if filters.status is not None:
            projects = [p for p in projects if p.status == filters.status]
        if filters.designated_user_id is not None:
            projects = [p for p in projects if p.designated_user_id == filters.designated_user_id]
        if filters.project_number:
            projects = [
                p for p in projects if filters.project_number.lower() in p.project_number.lower()
            ]
        total = len(projects)
        skip = filters.skip or 0
        limit = filters.limit
        return total, projects[skip : skip + limit if limit else None]

    async def save(self, project: Project) -> Project:
        if project.id == 0:
            project.id = self._next_id
            self._next_id += 1
        self._projects[project.id] = project
        return project

    async def get_live_work(self, project_id: int) -> ProjectLiveWork:
        return ProjectLiveWork()

    async def delete(self, project: Project) -> None:
        self._projects.pop(project.id, None)


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None):
        self._users: dict[int, User] = {u.id: u for u in (users or [])}

    async def get_by_id(self, id: int):
        return self._users.get(id)

    async def get_by_username(self, username: str):
        return next((u for u in self._users.values() if u.username == username), None)

    async def get_by_email(self, email: str):
        return next((u for u in self._users.values() if u.email == email), None)

    async def get_by_rfid(self, rfid: str):
        return None

    async def get_multi(self, filters):
        users = list(self._users.values())
        return len(users), users

    async def save(self, user):
        return user

    async def delete(self, user):
        pass


@dataclass
class FakeDemandItem:
    """Minimal stand-in for MadeItemDemandItem/BoughtItemDemandItem, only
    the fields UpdateProject's delivery-date propagation touches."""

    id: int
    project_id: int
    status: str
    desired_delivery_date: date | None = None
    changed: date | None = None
    changes: list[str] = field(default_factory=list)


class FakeDemandRepository:
    """Minimal fake for I{Made,Bought}ItemDemandItemRepository, project
    tests only exercise get_by_project_id and the save. `saved` records the
    ids of the demands written."""

    def __init__(self, items: list[FakeDemandItem] | None = None):
        self._items = list(items or [])
        self.saved: list[int] = []

    @property
    def items(self) -> list[FakeDemandItem]:
        """The stored demand items, for assertions."""
        return self._items

    async def get_by_project_id(self, project_id: int) -> list[FakeDemandItem]:
        return [i for i in self._items if i.project_id == project_id]

    async def save(self, item: FakeDemandItem) -> FakeDemandItem:
        self.saved.append(item.id)
        return item


FakeMadeItemDemandRepository = FakeDemandRepository
FakeBoughtItemDemandRepository = FakeDemandRepository


@dataclass
class FakeAllocation:
    """Minimal stand-in for MadeItemDemandAllocation, only the fields the
    lot-delivery-date cascade reads."""

    demand_item_id: int
    lot_id: int | None


class FakeMadeItemAllocationRepository:
    def __init__(self, allocations: list[FakeAllocation] | None = None):
        self._allocations = list(allocations or [])

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[FakeAllocation]:
        ids = set(demand_item_ids)
        return [a for a in self._allocations if a.demand_item_id in ids]


@dataclass
class FakeLot:
    """Minimal stand-in for ProductionLot, only the fields the
    delivery-date cascade touches."""

    id: int
    status: str
    required_delivery_date: date | None = None
    changed: datetime | None = None
    changes: list[str] = field(default_factory=list)


class FakeLotRepository:
    def __init__(self, lots: list[FakeLot] | None = None):
        self._lots: dict[int, FakeLot] = {lot.id: lot for lot in (lots or [])}

    async def get_by_ids(self, ids: list[int]) -> list[FakeLot]:
        return [self._lots[i] for i in ids if i in self._lots]

    async def get_multi(self, filters):
        return 0, []

    async def get_by_project_id(self, project_id: int, *, refresh: bool = False) -> list[FakeLot]:
        return []

    async def lock_time_budgets(self, project_id: int) -> None:
        return None

    async def save_step_time_budgets(self, budgets: dict[int, float | None]) -> None:
        return None

    async def save(self, lot: FakeLot) -> FakeLot:
        return lot


# ── CreateProject tests ───────────────────────────────────────────────


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


async def _record(order: list[str], step: str) -> None:
    order.append(step)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.commits = 0
        self.rolled_back = False

    async def commit(self):
        self.committed = True
        self.commits += 1

    async def rollback(self):
        self.rolled_back = True


class FakeSettingsRepository:
    """Only get_general() is exercised, the project use cases read nothing else."""

    def __init__(
        self, project_number_pattern: str = "", allow_headless_projects: bool = True
    ) -> None:
        self.general = AdminGeneralSettings(
            id=1,
            company_name=None,
            company_legal_name=None,
            company_logo_key=None,
            contact_email=None,
            imprint_url=None,
            privacy_url=None,
            support_url=None,
            product_number_pattern="",
            project_number_pattern=project_number_pattern,
            allow_headless_projects=allow_headless_projects,
            empty_value_placeholder="-",
            office_launcher_enabled=False,
            office_sharepoint_url="",
            default_language=Language.enGB,
            default_timezone="Europe/Vienna",
            default_date_format=DateFormat.ISO,
            currency="EUR",
        )

    async def get_general(self) -> AdminGeneralSettings:
        return self.general


class TestCreateProject:
    def setup_method(self):
        self.manager = make_user(
            id=1,
            username="manager",
            permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS],
        )
        self.normal = make_user(id=2, username="normal", permissions=[Permission.WRITE_PROJECTS])
        self.unprivileged = make_user(id=3, username="unprivileged", permissions=[])
        self.project_repo = FakeProjectRepository()
        self.user_repo = FakeUserRepository(users=[self.manager, self.normal, self.unprivileged])
        self.bus = FakeEventBus()
        self.settings_repo = FakeSettingsRepository()
        self.uow = FakeUnitOfWork()
        self.use_case = CreateProject(
            self.project_repo,
            self.user_repo,
            event_bus=self.bus,
            settings_repo=self.settings_repo,
            uow=self.uow,
        )

    def _cmd(self, **kwargs) -> CreateProjectCommand:
        defaults = dict(
            project_number="P-001",
            customer_id=None,
            product_id=None,
            description="Test",
            designated_user_id=1,
        )
        defaults.update(kwargs)
        return CreateProjectCommand(**defaults)

    async def test_manager_can_create(self):
        result = await self.use_case.execute(actor=self.manager, cmd=self._cmd())
        assert result.project_number == "P-001"
        assert result.id > 0
        (event,) = self.bus.published
        assert event.project_number == "P-001"

    async def test_event_is_staged_before_the_commit(self):
        # The transactional bus stages the event in the open transaction, so
        # it must be published before the unit of work commits.
        order: list[str] = []
        self.bus.publish = lambda event: _record(order, "publish")
        self.uow.commit = lambda: _record(order, "commit")

        await self.use_case.execute(actor=self.manager, cmd=self._cmd())

        assert order == ["publish", "commit"]

    async def test_normal_user_can_create(self):
        result = await self.use_case.execute(actor=self.normal, cmd=self._cmd())
        assert result.id > 0

    async def test_unprivileged_user_cannot_create(self):
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=self.unprivileged, cmd=self._cmd())

    async def test_duplicate_number_raises(self):
        await self.project_repo.save(make_project(id=1, project_number="P-001"))
        with pytest.raises(ProjectAlreadyExistsError):
            await self.use_case.execute(actor=self.manager, cmd=self._cmd(project_number="P-001"))

    async def test_nonexistent_designated_user_raises(self):
        with pytest.raises(UserNotFoundError):
            await self.use_case.execute(actor=self.manager, cmd=self._cmd(designated_user_id=999))

    async def test_number_pattern_rejects_mismatch(self):
        self.settings_repo.general.project_number_pattern = r"P-\d{3}"
        with pytest.raises(ProjectNumberPatternError):
            await self.use_case.execute(actor=self.manager, cmd=self._cmd(project_number="XYZ"))

    async def test_number_pattern_accepts_match(self):
        self.settings_repo.general.project_number_pattern = r"P-\d{3}"
        result = await self.use_case.execute(
            actor=self.manager, cmd=self._cmd(project_number="P-042")
        )
        assert result.project_number == "P-042"

    async def test_number_pattern_is_full_match(self):
        """An unanchored pattern must not accept a number that merely contains it."""
        self.settings_repo.general.project_number_pattern = r"P-\d{3}"
        with pytest.raises(ProjectNumberPatternError):
            await self.use_case.execute(
                actor=self.manager, cmd=self._cmd(project_number="XXP-001YY")
            )

    async def test_empty_pattern_accepts_anything(self):
        result = await self.use_case.execute(
            actor=self.manager, cmd=self._cmd(project_number="~!@#")
        )
        assert result.project_number == "~!@#"

    async def test_headless_rejected_when_disallowed(self):
        self.settings_repo.general.allow_headless_projects = False
        with pytest.raises(ProjectProductRequiredError):
            await self.use_case.execute(actor=self.manager, cmd=self._cmd(product_id=None))

    async def test_headless_allowed_by_default(self):
        result = await self.use_case.execute(actor=self.manager, cmd=self._cmd(product_id=None))
        assert result.product_id is None

    async def test_normal_user_always_assigned_to_self(self):
        """Users without manage:projects cannot assign the project to someone else."""
        result = await self.use_case.execute(
            actor=self.normal, cmd=self._cmd(designated_user_id=self.manager.id)
        )
        assert result.designated_user_id == self.normal.id

    async def test_manager_can_assign_to_other_user(self):
        result = await self.use_case.execute(
            actor=self.manager, cmd=self._cmd(designated_user_id=self.normal.id)
        )
        assert result.designated_user_id == self.normal.id

    async def test_create_records_a_creation_changelog_entry(self):
        result = await self.use_case.execute(actor=self.manager, cmd=self._cmd())

        assert len(result.changes) == 1
        assert result.changes[0].endswith("Project created.")
        assert self.manager.full_name in result.changes[0]

    async def test_create_stamps_changed_alongside_created(self):
        # A project whose history starts at creation must also carry a
        # `changed` timestamp; useChangedByUser on the frontend resolves the
        # last changelog entry's author and would otherwise show nothing at
        # all for a project nobody has edited yet.
        result = await self.use_case.execute(actor=self.manager, cmd=self._cmd())

        assert result.changed == result.created

    async def test_creation_entry_matches_the_frontend_parse_contract(self):
        # parseChangelogEntry() splits on ", " and reads the author out of
        # field 1, so the entry must stay "<timestamp>, <full name>, <message>".
        result = await self.use_case.execute(actor=self.manager, cmd=self._cmd())

        assert result.changes[0].split(", ")[1] == self.manager.full_name


# ── UpdateProject tests ───────────────────────────────────────────────


class TestUpdateProject:
    def setup_method(self):
        self.manager = make_user(
            id=1,
            username="manager",
            permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS],
        )
        self.designated = make_user(
            id=2, username="designated", permissions=[Permission.WRITE_PROJECTS]
        )
        self.other = make_user(id=3, username="other", permissions=[Permission.WRITE_PROJECTS])
        self.project = make_project(id=1, project_number="P-001", designated_user_id=2)
        self.project_repo = FakeProjectRepository(projects=[self.project])
        self.user_repo = FakeUserRepository(users=[self.manager, self.designated, self.other])
        self.made_demand_repo = FakeMadeItemDemandRepository()
        self.bought_demand_repo = FakeBoughtItemDemandRepository()
        self.made_allocation_repo = FakeMadeItemAllocationRepository()
        self.lot_repo = FakeLotRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.settings_repo = FakeSettingsRepository()
        self.lock_plan = FakeLockPlan()
        self.use_case = UpdateProject(
            self.project_repo,
            self.user_repo,
            uow=self.uow,
            event_bus=self.bus,
            settings_repo=self.settings_repo,
            work=self.project_repo,
            propagation=ProjectWorkPropagation(
                self.project_repo,
                lot_repo=self.lot_repo,
                made_demand_repo=self.made_demand_repo,
                bought_demand_repo=self.bought_demand_repo,
                made_allocation_repo=self.made_allocation_repo,
                lock_plan=self.lock_plan,
                order_repo=FakeProductionOrderRepository(),
            ),
        )

    def _cmd(self, **kwargs) -> UpdateProjectCommand:
        defaults = dict(
            project_number="P-001",
            customer_id=None,
            product_id=None,
            description="Updated",
            designated_user_id=2,
            status="active",
        )
        defaults.update(kwargs)
        return UpdateProjectCommand(**defaults)

    async def test_manager_can_update(self):
        result = await self.use_case.execute(
            actor=self.manager, project_id=1, cmd=self._cmd(description="New desc")
        )
        assert result.description == "New desc"

    async def test_designated_user_can_update(self):
        result = await self.use_case.execute(
            actor=self.designated, project_id=1, cmd=self._cmd(description="Updated by designated")
        )
        assert result.description == "Updated by designated"

    async def test_non_designated_user_without_manage_cannot_update(self):
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=self.other, project_id=1, cmd=self._cmd())

    async def test_project_not_found_raises(self):
        with pytest.raises(ProjectNotFoundError):
            await self.use_case.execute(actor=self.manager, project_id=999, cmd=self._cmd())

    async def test_duplicate_number_raises(self):
        await self.project_repo.save(
            make_project(id=2, project_number="P-002", designated_user_id=1)
        )
        with pytest.raises(ProjectAlreadyExistsError):
            await self.use_case.execute(
                actor=self.manager, project_id=1, cmd=self._cmd(project_number="P-002")
            )

    async def test_nonexistent_designated_user_raises(self):
        with pytest.raises(UserNotFoundError):
            await self.use_case.execute(
                actor=self.manager, project_id=1, cmd=self._cmd(designated_user_id=999)
            )

    async def test_number_pattern_rejects_changed_number(self):
        self.settings_repo.general.project_number_pattern = r"P-\d{3}"
        with pytest.raises(ProjectNumberPatternError):
            await self.use_case.execute(
                actor=self.manager, project_id=1, cmd=self._cmd(project_number="XYZ")
            )

    async def test_number_pattern_ignores_unchanged_legacy_number(self):
        """A row that predates the pattern stays editable as long as its number is left alone."""
        self.project.project_number = "LEGACY-1"
        self.settings_repo.general.project_number_pattern = r"P-\d{3}"
        result = await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(project_number="LEGACY-1", description="New desc"),
        )
        assert result.description == "New desc"

    async def test_removing_product_rejected_when_headless_disallowed(self):
        self.project.product_id = 7
        self.settings_repo.general.allow_headless_projects = False
        with pytest.raises(ProjectProductRequiredError):
            await self.use_case.execute(
                actor=self.manager, project_id=1, cmd=self._cmd(product_id=None)
            )

    async def test_already_headless_project_stays_editable(self):
        """Turning the setting off must not freeze projects that were already headless."""
        self.project.product_id = None
        self.settings_repo.general.allow_headless_projects = False
        result = await self.use_case.execute(
            actor=self.manager, project_id=1, cmd=self._cmd(product_id=None, description="New desc")
        )
        assert result.description == "New desc"

    async def test_update_records_changed_timestamp_and_changelog_entry(self):
        assert self.project.changed is None
        assert self.project.changes == []

        result = await self.use_case.execute(
            actor=self.manager, project_id=1, cmd=self._cmd(description="New desc")
        )

        assert result.changed is not None
        assert result.changes
        entry = diff_entry(result.changes)
        assert "manager" not in entry  # username isn't logged, full_name is
        assert self.manager.full_name in entry
        assert "description" in entry

    async def test_update_with_designated_user_omitted_does_not_log_a_false_change(self):
        # designated_user_id omitted → "leave the owner alone" (see the use
        # case's own comment); the changelog diff must compare against the
        # *resolved* value, not raw cmd.designated_user_id (which is None
        # here even though nothing about the owner changed).
        result = await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(description="New desc", designated_user_id=None),
        )

        assert result.designated_user_id == 2
        assert "designated_user_id" not in diff_entry(result.changes)

    async def test_update_with_no_actual_changes_logs_no_changes(self):
        # cmd defaults already mirror every field on `self.project` except
        # description; pin that one too so this is a true no-op update.
        result = await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(description=self.project.description),
        )

        assert diff_entry(result.changes).endswith("No changes.")

    async def test_delivery_dates_round_trip_and_are_logged(self):
        result = await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=date(2026, 9, 1),
                required_delivery_date_bought=date(2026, 9, 15),
            ),
        )

        assert result.required_delivery_date_made == date(2026, 9, 1)
        assert result.required_delivery_date_bought == date(2026, 9, 15)
        entry = diff_entry(result.changes)
        assert "required_delivery_date_made" in entry
        assert "required_delivery_date_bought" in entry

    async def test_clearing_a_delivery_date_does_not_propagate(self):
        self.project.required_delivery_date_made = date(2026, 9, 1)
        self.made_demand_repo._items.append(FakeDemandItem(id=1, project_id=1, status="open"))

        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=None,
                propagate_delivery_date_made=True,
            ),
        )

        # Nothing propagated: no demand was written, and the one commit
        # carries only the project's own update.
        assert self.made_demand_repo.items[0].desired_delivery_date is None
        assert self.made_demand_repo.saved == []
        assert self.uow.commits == 1

    async def test_propagation_updates_only_non_terminal_demands(self):
        open_demand = FakeDemandItem(id=1, project_id=1, status="open")
        allocated_demand = FakeDemandItem(id=2, project_id=1, status="allocated")
        fulfilled_demand = FakeDemandItem(id=3, project_id=1, status="fulfilled")
        canceled_demand = FakeDemandItem(id=4, project_id=1, status="canceled")
        other_project_demand = FakeDemandItem(id=5, project_id=2, status="open")
        self.made_demand_repo._items.extend(
            [open_demand, allocated_demand, fulfilled_demand, canceled_demand, other_project_demand]
        )

        new_date = date(2026, 10, 1)
        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=new_date,
                propagate_delivery_date_made=True,
            ),
        )

        assert open_demand.desired_delivery_date == new_date
        assert allocated_demand.desired_delivery_date == new_date
        assert fulfilled_demand.desired_delivery_date is None
        assert canceled_demand.desired_delivery_date is None
        assert other_project_demand.desired_delivery_date is None
        assert "Desired delivery date" in open_demand.changes[0]
        assert sorted(self.made_demand_repo.saved) == [1, 2]
        assert self.uow.commits == 1

    async def test_propagation_records_a_summary_entry_on_the_project(self):
        # The field diff alone says the project's date moved; it does not say
        # that N demands and M lots were rewritten as a side effect. Without
        # this the blast radius is only discoverable by reading every child.
        self.made_demand_repo._items.extend(
            [
                FakeDemandItem(id=1, project_id=1, status="open"),
                FakeDemandItem(id=2, project_id=1, status="allocated"),
            ]
        )
        lot = FakeLot(id=10, status="planned", required_delivery_date=None)
        self.lot_repo._lots[10] = lot
        self.made_allocation_repo._allocations.append(FakeAllocation(demand_item_id=1, lot_id=10))

        result = await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=date(2026, 10, 1),
                propagate_delivery_date_made=True,
            ),
        )

        summary = result.changes[-1]
        assert "Propagated made delivery date 2026-10-01" in summary
        assert "2 demand(s)" in summary
        assert "1 lot(s)" in summary

    async def test_no_summary_entry_when_nothing_propagated(self):
        # Flag set, but no demands to touch; the project should carry the
        # field diff and nothing else.
        result = await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=date(2026, 10, 1),
                propagate_delivery_date_made=True,
            ),
        )

        assert len(result.changes) == 1
        assert "Propagated" not in result.changes[0]

    async def test_no_propagation_without_flag(self):
        demand = FakeDemandItem(id=1, project_id=1, status="open")
        self.made_demand_repo._items.append(demand)

        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(required_delivery_date_made=date(2026, 10, 1)),
        )

        # Nothing propagated: no demand was written, and the one commit
        # carries only the project's own update.
        assert demand.desired_delivery_date is None
        assert self.made_demand_repo.saved == []
        assert self.uow.commits == 1

    async def test_no_propagation_when_date_unchanged(self):
        self.project.required_delivery_date_bought = date(2026, 10, 1)
        demand = FakeDemandItem(id=1, project_id=1, status="open")
        self.bought_demand_repo._items.append(demand)

        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_bought=date(2026, 10, 1),
                propagate_delivery_date_bought=True,
            ),
        )

        # Nothing propagated: no demand was written, and the one commit
        # carries only the project's own update.
        assert demand.desired_delivery_date is None
        assert self.bought_demand_repo.saved == []
        assert self.uow.commits == 1

    async def test_propagation_fills_in_required_delivery_date_on_existing_lot(self):
        # Regression: a demand allocated to a lot BEFORE the project's date
        # propagates must still have that lot's own (unset) date filled in,
        # not just the demand's.
        demand = FakeDemandItem(id=1, project_id=1, status="allocated")
        self.made_demand_repo._items.append(demand)
        lot = FakeLot(id=10, status="planned", required_delivery_date=None)
        self.lot_repo._lots[10] = lot
        self.made_allocation_repo._allocations.append(FakeAllocation(demand_item_id=1, lot_id=10))

        new_date = date(2026, 10, 1)
        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(required_delivery_date_made=new_date, propagate_delivery_date_made=True),
        )

        assert lot.required_delivery_date == new_date
        assert "Required delivery date" in lot.changes[-1]

    async def test_propagation_overwrites_a_lot_date_derived_from_an_earlier_demand_date(self):
        # A lot's date has no provenance flag distinguishing "derived from
        # this demand at creation time" from "unset"; propagation must
        # overwrite it either way, the same "apply to all non-completed
        # items" the user just confirmed for the demands themselves.
        demand = FakeDemandItem(id=1, project_id=1, status="allocated")
        self.made_demand_repo._items.append(demand)
        lot = FakeLot(id=10, status="planned", required_delivery_date=date(2026, 8, 1))
        self.lot_repo._lots[10] = lot
        self.made_allocation_repo._allocations.append(FakeAllocation(demand_item_id=1, lot_id=10))

        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=date(2026, 10, 1), propagate_delivery_date_made=True
            ),
        )

        assert lot.required_delivery_date == date(2026, 10, 1)

    async def test_propagation_skips_terminal_lots(self):
        demand = FakeDemandItem(id=1, project_id=1, status="allocated")
        self.made_demand_repo._items.append(demand)
        completed_lot = FakeLot(id=10, status="completed", required_delivery_date=None)
        canceled_lot = FakeLot(id=11, status="canceled", required_delivery_date=None)
        self.lot_repo._lots[10] = completed_lot
        self.lot_repo._lots[11] = canceled_lot
        self.made_allocation_repo._allocations.extend(
            [
                FakeAllocation(demand_item_id=1, lot_id=10),
                FakeAllocation(demand_item_id=1, lot_id=11),
            ]
        )

        await self.use_case.execute(
            actor=self.manager,
            project_id=1,
            cmd=self._cmd(
                required_delivery_date_made=date(2026, 10, 1), propagate_delivery_date_made=True
            ),
        )

        assert completed_lot.required_delivery_date is None
        assert canceled_lot.required_delivery_date is None


# ── DeleteProject tests ───────────────────────────────────────────────


class TestDeleteProject:
    def setup_method(self):
        self.manager = make_user(
            id=1,
            username="manager",
            permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS],
        )
        self.normal = make_user(id=2, username="normal", permissions=[Permission.WRITE_PROJECTS])
        self.project = make_project(id=1, project_number="P-001", designated_user_id=2)
        self.project_repo = FakeProjectRepository(projects=[self.project])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.use_case = DeleteProject(
            self.project_repo, event_bus=self.bus, uow=self.uow, work=self.project_repo
        )

    async def test_manager_can_delete(self):
        result = await self.use_case.execute(actor=self.manager, project_id=1)
        assert result.deleted is True
        assert result.status == "archived"
        (event,) = self.bus.published
        assert event.project_id == 1

    async def test_normal_user_cannot_delete(self):
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=self.normal, project_id=1)

    async def test_project_not_found_raises(self):
        with pytest.raises(ProjectNotFoundError):
            await self.use_case.execute(actor=self.manager, project_id=999)

    async def test_delete_appends_a_changelog_entry(self):
        # The archive transition never goes through UpdateProject, so without
        # this the project's own history ends at the last edit and never
        # records that it was archived at all.
        result = await self.use_case.execute(actor=self.manager, project_id=1)

        assert result.changes[-1].endswith("Project deleted.")
        assert self.manager.full_name in result.changes[-1]
        assert result.changed is not None

    async def test_delete_preserves_existing_history(self):
        self.project.changes = ["2026-01-01 00:00:00, Someone, Project created."]

        result = await self.use_case.execute(actor=self.manager, project_id=1)

        assert len(result.changes) == 2
        assert result.changes[0].endswith("Project created.")


# ── GetProject tests ──────────────────────────────────────────────────


class TestGetProject:
    def setup_method(self):
        self.projects = [
            make_project(id=1, project_number="P-001", designated_user_id=1),
            make_project(id=2, project_number="P-002", designated_user_id=1),
            make_project(id=3, project_number="P-003", designated_user_id=2),
        ]
        self.repo = FakeProjectRepository(projects=self.projects)

    async def test_get_by_id(self):
        result = await GetProject(self.repo).execute(project_id=1)
        assert result.project_number == "P-001"

    async def test_get_nonexistent_raises(self):
        with pytest.raises(ProjectNotFoundError):
            await GetProject(self.repo).execute(project_id=999)

    async def test_get_by_number(self):
        result = await GetProjectByNumber(self.repo).execute(number="P-002")
        assert result.id == 2

    async def test_get_my_projects(self):
        results = await GetMyProjects(self.repo).execute(user_id=1)
        assert len(results) == 2

    async def test_get_multi_no_filter(self):
        result = await GetProjects(self.repo).execute(filters=ProjectFilterDto())
        assert result.total == 3

    async def test_get_multi_filter_by_designated_user(self):
        result = await GetProjects(self.repo).execute(
            filters=ProjectFilterDto(designated_user_id=2)
        )
        assert result.total == 1
        assert result.items[0].project_number == "P-003"

    async def test_get_multi_excludes_deleted(self):
        deleted = make_project(id=4, project_number="P-004", deleted=True)
        await self.repo.save(deleted)
        result = await GetProjects(self.repo).execute(filters=ProjectFilterDto())
        assert result.total == 3  # deleted project excluded
