"""
Unit tests for made-item demand use cases (create, update, delete/cancel).
Mirrors test_demand_item_use_cases.py. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.fulfillment.application.dto.made_item_demand_dto import CreateMadeItemDemandCommand
from src.modules.fulfillment.application.dto.made_item_demand_dto import UpdateMadeItemDemandCommand
from src.modules.fulfillment.application.use_cases.made_item_demand.create_demand_item import (
    CreateDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.delete_demand_item import (
    DeleteDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demands_pipeline import (
    GetDemandsPipeline,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item import (
    UpdateDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemInvalidAlterationError
from src.modules.fulfillment.domain.errors import DemandItemInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import DemandItemOfAnotherUserError
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler

# ── Helpers ───────────────────────────────────────────────────────────


def make_made_item(
    id: int = 1,
    article_name: str = "Bracket",
    status: MadeItemCatalogueStatus = MadeItemCatalogueStatus.ACTIVE,
) -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        revision="A",
        revision_date=None,
        revision_note=None,
        article_name=article_name,
        status=status,
        data_source=DataSource.WEB,
        part_number=None,
        material="1.0037",
        mass=None,
        base_size=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        bought_item_id=None,
        source_item_id=None,
        article_group_ids=[],
        successor_item_id=None,
        changed_by_id=None,
    )


def make_project(
    id: int = 1,
    project_number: str = "P-001",
    status: ProjectStatus = ProjectStatus.ACTIVE,
    required_delivery_date_made: date | None = None,
) -> Project:
    return Project(
        id=id,
        project_number=project_number,
        description="Test project",
        status=status,
        designated_user_id=1,
        created=datetime.now(UTC),
        required_delivery_date_made=required_delivery_date_made,
        deleted=False,
    )


def make_demand(
    id: int = 1,
    creator_id: int = 1,
    made_item_id: int = 1,
    project_id: int = 1,
    status: MadeItemDemandStatus = MadeItemDemandStatus.OPEN,
    item_part_number: str = "",
    item_revision: str = "",
) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=5.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=creator_id,
        made_item_id=made_item_id,
        project_id=project_id,
        item_part_number=item_part_number,
        item_revision=item_revision,
    )


class FakeDemandRepository:
    def __init__(self, demands: list[MadeItemDemandItem] | None = None):
        self._demands: dict[int, MadeItemDemandItem] = {}
        self._next_id = 1
        for d in demands or []:
            self._demands[d.id] = d
            self._next_id = max(self._next_id, d.id + 1)
        self._deleted: list[int] = []

    @property
    def deleted(self) -> list[int]:
        """The ids of the demands deleted so far, for assertions."""
        return self._deleted

    async def get_by_id(self, id: int) -> MadeItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> MadeItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_ids(self, ids: list[int]) -> list[MadeItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem:
        if demand.id == 0:
            demand.id = self._next_id
            self._next_id += 1
        self._demands[demand.id] = demand
        return demand

    async def delete(self, demand: MadeItemDemandItem) -> None:
        self._deleted.append(demand.id)
        self._demands.pop(demand.id, None)

    async def get_by_project_id(self, project_id: int) -> list[MadeItemDemandItem]:
        raise NotImplementedError

    async def get_pipeline(self, terminal_since: date) -> list[MadeItemDemandItem]:
        raise NotImplementedError

    async def get_multi(
        self, filters: MadeItemDemandFilterDto
    ) -> tuple[int, list[MadeItemDemandItem]]:
        raise NotImplementedError


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None):
        self._items: dict[int, MadeItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> MadeItem | None:
        return self._items.get(id)

    async def get_multi(self, filters: MadeItemFilterDto) -> tuple[int, list[MadeItem]]:
        raise NotImplementedError

    async def save(self, item: MadeItem) -> MadeItem:
        raise NotImplementedError

    async def delete(self, item: MadeItem) -> None:
        raise NotImplementedError

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError

    async def get_processes(self, made_item_id: int) -> list:
        raise NotImplementedError

    async def get_process_by_id(self, process_id: int):
        raise NotImplementedError

    async def save_process(self, process):
        raise NotImplementedError

    async def delete_process(self, process) -> None:
        raise NotImplementedError

    async def reorder_processes(self, made_item_id: int, ordered_process_ids: list[int]) -> list:
        raise NotImplementedError


class FakeProjectRepository:
    def __init__(self, projects: list[Project] | None = None):
        self._projects: dict[int, Project] = {p.id: p for p in (projects or [])}

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        return None

    async def get_by_id(self, id: int) -> Project | None:
        return self._projects.get(id)

    async def get_by_project_number(self, number: str) -> Project | None:
        raise NotImplementedError

    async def get_by_product_id(self, product_id: int) -> list[Project]:
        raise NotImplementedError

    async def get_by_designated_user_id(self, user_id: int) -> list[Project]:
        raise NotImplementedError

    async def get_multi(self, filters: ProjectFilterDto) -> tuple[int, list[Project]]:
        raise NotImplementedError

    async def save(self, project: Project) -> Project:
        raise NotImplementedError

    async def delete(self, project: Project) -> None:
        raise NotImplementedError


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


# ── CreateDemandItem ──────────────────────────────────────────────────


class TestCreateDemandItem:
    def setup_method(self):
        self.item = make_made_item(id=1)
        self.project = make_project(id=1)
        self.demand_repo = FakeDemandRepository()
        self.item_repo = FakeMadeItemRepository([self.item])
        self.project_repo = FakeProjectRepository([self.project])
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.bus = FakeEventBus()
        self.use_case = CreateDemandItem(
            self.demand_repo,
            self.item_repo,
            self.project_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )

    def _cmd(self, **kwargs) -> CreateMadeItemDemandCommand:
        defaults = dict(made_item_id=1, project_id=1, quantity=5.0, unit="pcs")
        defaults.update(kwargs)
        return CreateMadeItemDemandCommand(**defaults)

    async def test_creates_demand_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.id > 0
        assert result.quantity == 5.0

    async def test_event_carries_correct_ids(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert event.demand_id == result.id
        assert event.made_item_id == 1
        assert event.project_id == 1
        assert event.creator_id == self.actor.id

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_item_not_found_raises(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(made_item_id=999))

    async def test_inactive_item_raises(self):
        inactive_item_repo = FakeMadeItemRepository(
            [make_made_item(id=2, status=MadeItemCatalogueStatus.INACTIVE)]
        )
        use_case = CreateDemandItem(
            self.demand_repo,
            inactive_item_repo,
            self.project_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )
        with pytest.raises(MadeItemInactiveError):
            await use_case.execute(actor=self.actor, cmd=self._cmd(made_item_id=2))

    async def test_project_not_found_raises(self):
        with pytest.raises(ProjectNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(project_id=999))

    def test_zero_quantity_rejected_by_dto(self):
        with pytest.raises(Exception):  # noqa: B017
            self._cmd(quantity=0)

    async def test_omitted_date_falls_back_to_project_default(self):
        project = make_project(id=2, required_delivery_date_made=date(2026, 9, 1))
        project_repo = FakeProjectRepository([project])
        use_case = CreateDemandItem(
            self.demand_repo,
            self.item_repo,
            project_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )
        cmd = CreateMadeItemDemandCommand(made_item_id=1, project_id=2, quantity=5.0, unit="pcs")

        result = await use_case.execute(actor=self.actor, cmd=cmd)

        assert result.desired_delivery_date == date(2026, 9, 1)

    async def test_explicit_null_date_does_not_fall_back(self):
        project = make_project(id=2, required_delivery_date_made=date(2026, 9, 1))
        project_repo = FakeProjectRepository([project])
        use_case = CreateDemandItem(
            self.demand_repo,
            self.item_repo,
            project_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )
        cmd = self._cmd(project_id=2, desired_delivery_date=None)

        result = await use_case.execute(actor=self.actor, cmd=cmd)

        assert result.desired_delivery_date is None

    async def test_explicit_date_wins_over_project_default(self):
        project = make_project(id=2, required_delivery_date_made=date(2026, 9, 1))
        project_repo = FakeProjectRepository([project])
        use_case = CreateDemandItem(
            self.demand_repo,
            self.item_repo,
            project_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )
        cmd = self._cmd(project_id=2, desired_delivery_date=date(2026, 12, 25))

        result = await use_case.execute(actor=self.actor, cmd=cmd)

        assert result.desired_delivery_date == date(2026, 12, 25)

    async def test_alteration_requires_target_item(self):
        with pytest.raises(DemandItemInvalidAlterationError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(is_alteration=True))

    async def test_alteration_target_must_differ_from_made_item(self):
        with pytest.raises(DemandItemInvalidAlterationError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(is_alteration=True, alteration_of_made_item_id=1),
            )

    async def test_alteration_target_must_be_unset_when_not_alteration(self):
        with pytest.raises(DemandItemInvalidAlterationError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(is_alteration=False, alteration_of_made_item_id=2),
            )

    async def test_alteration_target_must_exist(self):
        with pytest.raises(MadeItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=self._cmd(is_alteration=True, alteration_of_made_item_id=999),
            )

    async def test_valid_alteration_succeeds(self):
        item_repo = FakeMadeItemRepository([self.item, make_made_item(id=2)])
        use_case = CreateDemandItem(
            self.demand_repo,
            item_repo,
            self.project_repo,
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )
        result = await use_case.execute(
            actor=self.actor,
            cmd=self._cmd(is_alteration=True, alteration_of_made_item_id=2),
        )
        assert result.is_alteration is True
        assert result.alteration_of_made_item_id == 2


# ── UpdateDemandItem ──────────────────────────────────────────────────


class TestUpdateDemandItem:
    def setup_method(self):
        self.owner = make_user(id=1, permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.other = make_user(id=2, username="other", permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.manager = make_user(
            id=3,
            username="mgr",
            permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
        )
        self.demand = make_demand(id=1, creator_id=1, status=MadeItemDemandStatus.OPEN)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.made_item_repo = FakeMadeItemRepository()
        self.use_case = UpdateDemandItem(
            self.demand_repo,
            self.made_item_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )

    def _cmd(self, **kwargs) -> UpdateMadeItemDemandCommand:
        defaults = dict(quantity=10.0, unit="pcs")
        defaults.update(kwargs)
        return UpdateMadeItemDemandCommand(**defaults)

    async def test_owner_can_update(self):
        result = await self.use_case.execute(
            actor=self.owner, demand_id=1, cmd=self._cmd(quantity=10.0)
        )
        assert result.quantity == 10.0

    async def test_manager_can_update_others_demand(self):
        result = await self.use_case.execute(
            actor=self.manager, demand_id=1, cmd=self._cmd(quantity=7.0)
        )
        assert result.quantity == 7.0

    async def test_other_user_without_manage_cannot_update(self):
        with pytest.raises(DemandItemOfAnotherUserError):
            await self.use_case.execute(actor=self.other, demand_id=1, cmd=self._cmd())

    async def test_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(actor=self.owner, demand_id=999, cmd=self._cmd())

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, demand_id=1, cmd=self._cmd())

    async def test_fulfilled_demand_cannot_be_updated_without_manage(self):
        fulfilled = make_demand(id=2, creator_id=1, status=MadeItemDemandStatus.FULFILLED)
        await self.demand_repo.save(fulfilled)
        with pytest.raises(DemandItemAlreadyFulfilledError):
            await self.use_case.execute(actor=self.owner, demand_id=2, cmd=self._cmd())

    async def test_canceled_demand_cannot_be_updated_without_manage(self):
        canceled = make_demand(id=3, creator_id=1, status=MadeItemDemandStatus.CANCELED)
        await self.demand_repo.save(canceled)
        with pytest.raises(DemandItemAlreadyCanceledError):
            await self.use_case.execute(actor=self.owner, demand_id=3, cmd=self._cmd())

    async def test_manager_cannot_update_fulfilled_demand(self):
        fulfilled = make_demand(id=2, creator_id=1, status=MadeItemDemandStatus.FULFILLED)
        await self.demand_repo.save(fulfilled)
        quantity_before = fulfilled.quantity
        with pytest.raises(DemandItemAlreadyFulfilledError):
            await self.use_case.execute(
                actor=self.manager, demand_id=2, cmd=self._cmd(quantity=3.0)
            )
        assert (await self.demand_repo.get_by_id(2)).quantity == quantity_before


# ── UpdateDemandItemStatus ────────────────────────────────────────────


class _StubCancelMadeItemDemand:
    """Records whether the CANCELED delegation was reached at all. The
    permission gate must run BEFORE it."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def execute_permitted(self, actor, demand_id: int):
        self.calls.append(demand_id)
        raise AssertionError("cancel delegation should not have been reached")


class TestUpdateDemandItemStatus:
    """Permission tests for this use case: it checks the permission itself
    rather than relying on the CANCELED delegation, whose own gate depends
    on a live lot."""

    def setup_method(self):
        self.owner = make_user(id=1, permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.other = make_user(id=2, username="other", permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.manager = make_user(
            id=3,
            username="mgr",
            permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
        )
        self.demand = make_demand(id=1, creator_id=1, status=MadeItemDemandStatus.ALLOCATED)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.bus = FakeEventBus()
        self.cancel = _StubCancelMadeItemDemand()
        self.use_case = UpdateDemandItemStatus(
            self.demand_repo,
            self.cancel,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(made_demands=self.demand_repo),
        )

    async def test_requires_permission(self):
        permissionless = make_user(id=4, username="nobody", permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=permissionless, demand_id=1, new_status="ordered")
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"

    async def test_permitted_actor_cannot_set_a_status_the_allocations_decide(self):
        with pytest.raises(DemandItemInvalidStatusTransitionError):
            await self.use_case.execute(actor=self.owner, demand_id=1, new_status="ordered")
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"

    async def test_another_users_demand_requires_manage(self):
        with pytest.raises(DemandItemOfAnotherUserError):
            await self.use_case.execute(actor=self.other, demand_id=1, new_status="ordered")
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"

    async def test_terminal_target_requires_manage(self):
        """FULFILLED/CANCELED are irreversible, so the owner alone is not
        enough: manage:demand_items is required."""
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=self.owner, demand_id=1, new_status="fulfilled")
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"

    async def test_cancel_is_gated_even_when_the_demand_has_no_lot(self):
        """The CANCELED path delegates to CancelMadeItemDemand, whose own gate
        depends on a live lot resolving. The new check runs first, so an
        unauthorized cancellation is refused before the delegation is even
        reached, regardless of any lot."""
        permissionless = make_user(id=4, username="nobody", permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=permissionless, demand_id=1, new_status="canceled")
        assert self.cancel.calls == []
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"


# ── DeleteDemandItem ──────────────────────────────────────────────────


class _NoAllocations:
    """The allocations of demands that hold none."""

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []


class TestDeleteDemandItem:
    def setup_method(self):
        self.owner = make_user(id=1, permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.other = make_user(id=2, username="other", permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.manager = make_user(
            id=3,
            username="mgr",
            permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
        )
        self.demand = make_demand(id=1, creator_id=1, status=MadeItemDemandStatus.OPEN)
        self.demand_repo = FakeDemandRepository([self.demand])
        self.use_case = DeleteDemandItem(self.demand_repo, _NoAllocations(), uow=FakeUnitOfWork())

    async def test_owner_can_cancel(self):
        await self.use_case.execute(actor=self.owner, demand_id=1)
        assert 1 in self.demand_repo.deleted

    async def test_manager_can_cancel_others(self):
        await self.use_case.execute(actor=self.manager, demand_id=1)
        assert 1 in self.demand_repo.deleted

    async def test_other_user_cannot_cancel(self):
        with pytest.raises(DemandItemOfAnotherUserError):
            await self.use_case.execute(actor=self.other, demand_id=1)

    async def test_not_found_raises(self):
        with pytest.raises(DemandItemNotFoundError):
            await self.use_case.execute(actor=self.owner, demand_id=999)

    async def test_fulfilled_cannot_be_canceled(self):
        fulfilled = make_demand(id=2, creator_id=1, status=MadeItemDemandStatus.FULFILLED)
        await self.demand_repo.save(fulfilled)
        with pytest.raises(DemandItemAlreadyFulfilledError):
            await self.use_case.execute(actor=self.owner, demand_id=2)

    async def test_already_canceled_raises(self):
        canceled = make_demand(id=3, creator_id=1, status=MadeItemDemandStatus.CANCELED)
        await self.demand_repo.save(canceled)
        with pytest.raises(DemandItemAlreadyCanceledError):
            await self.use_case.execute(actor=self.owner, demand_id=3)


# ── GetDemandsPipeline ───────────────────────────────────────────────────
#
# These two tiny fakes implement only the one repository
# method each it actually calls, rather than touching FakeDemandRepository
# above (whose own get_pipeline stub deliberately raises NotImplementedError).


class _FakePipelineDemandRepo:
    def __init__(self, demands: list[MadeItemDemandItem]) -> None:
        self._demands = demands

    async def get_pipeline(self, terminal_since: date) -> list[MadeItemDemandItem]:
        return self._demands


class _FakePipelineAllocationRepo:
    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return []


class TestGetDemandsPipeline:
    async def test_row_carries_item_part_number_and_revision(self):
        demand = make_demand(id=1, item_part_number="PN-PIPE", item_revision="C")
        use_case = GetDemandsPipeline(
            demand_repo=_FakePipelineDemandRepo([demand]),
            allocation_repo=_FakePipelineAllocationRepo(),
        )

        result = await use_case.execute(terminal_since=date(2026, 1, 1))

        assert len(result.items) == 1
        row = result.items[0]
        assert row.item_part_number == "PN-PIPE"
        assert row.item_revision == "C"
