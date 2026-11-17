"""
Unit tests for made-item batch demand import (Excel) validate/commit use
cases. No database, no HTTP. All dependencies replaced with in-memory
fakes. Mirrors tests/unit/test_batch_demand_items.py (the bought-item
equivalent), minus the order-code/manufacturer fallback cases (made items
have no second natural key), plus made-specific ones (missing revision,
inactive/replaced status warnings, event publishing).

This is a lookup-only importer: rows only ever create MadeItemDemandItem
rows against catalogue items that already exist. It never creates or
updates a MadeItem. See src/modules/fulfillment/application/use_cases/made_item_demand/
batch_demand_items.py for the resolution rules these tests pin down.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemCreated
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemBatchDemandRowInput
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    CommitBatchMadeItemDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    ValidateBatchMadeItemDemandRows,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.errors import BatchDemandRowInvalidError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler

# ── Helpers ───────────────────────────────────────────────────────────


def make_row(**overrides) -> MadeItemBatchDemandRowInput:
    """Default row resolves against `make_item()`'s defaults."""
    defaults = dict(
        row_index=0,
        project_number="P0001",
        quantity=10.0,
        part_number="PN-100",
        revision="A",
        article_name="Bracket",
    )
    defaults.update(overrides)
    return MadeItemBatchDemandRowInput(**defaults)


def make_item(
    id: int = 1,
    part_number: str | None = "PN-100",
    revision: str = "A",
    article_name: str = "Bracket",
    status: MadeItemCatalogueStatus = MadeItemCatalogueStatus.ACTIVE,
    archived: bool = False,
) -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        revision=revision,
        revision_date=None,
        revision_note=None,
        article_name=article_name,
        status=status,
        data_source=DataSource.WEB,
        part_number=part_number,
        material=None,
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
    project_number: str = "P0001",
    required_delivery_date_made: date | None = None,
) -> Project:
    return Project(
        id=id,
        created=datetime.now(UTC),
        project_number=project_number,
        required_delivery_date_made=required_delivery_date_made,
    )


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeMadeItemRepo:
    """Mirrors the real SQL repo's semantics closely enough for these tests:
    part_number is substring-prefiltered (real repo uses ILIKE '%term%'),
    deleted items are always excluded. _RowResolver then narrows to a
    normalized-exact part_number + revision match itself, same as the real
    repo's callers do today."""

    def __init__(self, items: list[MadeItem] | None = None):
        self._items: list[MadeItem] = list(items or [])
        self.save_calls: list[MadeItem] = []

    async def get_multi(self, filters: MadeItemFilterDto):
        results = [i for i in self._items if not i.archived]
        if filters.part_number:
            term = filters.part_number.lower()
            results = [i for i in results if i.part_number and term in i.part_number.lower()]
        return len(results), results

    async def save(self, item: MadeItem) -> MadeItem:
        self.save_calls.append(item)
        return item


class FakeDemandRepo:
    def __init__(self):
        self._demands: dict[int, MadeItemDemandItem] = {}
        self._next_id = 1

    @property
    def demands(self) -> dict[int, MadeItemDemandItem]:
        """The stored demands by id, for assertions."""
        return self._demands

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem:
        if demand.id == 0:
            demand.id = self._next_id
            self._next_id += 1
        self._demands[demand.id] = demand
        return demand


class FakeProjectRepo:
    def __init__(self, projects: list[Project] | None = None):
        self._projects = list(projects or [])

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        return None

    async def get_multi(self, filters: ProjectFilterDto):
        results = self._projects
        if filters.project_number:
            term = filters.project_number.lower()
            results = [p for p in results if term in p.project_number.lower()]
        return len(results), results

    async def get_by_id(self, id: int):
        return next((p for p in self._projects if p.id == id), None)


class FakeEventBus:
    def __init__(self):
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


class FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


# ── ValidateBatchMadeItemDemandRows ─────────────────────────────────────


class TestValidateBatchMadeItemDemandRows:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.project_repo = FakeProjectRepo([make_project()])

    def _use_case(self, items: list[MadeItem] | None = None) -> ValidateBatchMadeItemDemandRows:
        self.item_repo = FakeMadeItemRepo(items)
        return ValidateBatchMadeItemDemandRows(
            item_repo=self.item_repo,
            project_repo=self.project_repo,
        )

    # -- part number + revision match ----------------------------------

    async def test_part_number_and_revision_exact_match_case_and_whitespace_insensitive(self):
        use_case = self._use_case([make_item(part_number="PN-100", revision="A")])
        result = await use_case.execute(
            self.actor, [make_row(part_number="  pn-100  ", revision=" a ")]
        )
        row = result.results[0]
        assert row.row_status == "matched"
        assert row.match_source == "part_number_revision"
        assert row.matched_item.id == 1
        assert row.divergences == []
        assert result.all_valid

    async def test_same_part_number_different_revision_is_not_found(self):
        use_case = self._use_case([make_item(part_number="PN-100", revision="B")])
        result = await use_case.execute(self.actor, [make_row(part_number="PN-100", revision="A")])
        out = result.results[0]
        assert out.row_status == "not_found"
        assert out.matched_item is None
        assert not result.all_valid

    async def test_ambiguous_part_number_and_revision_blocks(self):
        use_case = self._use_case(
            [
                make_item(id=1, part_number="PN-DUP", revision="A"),
                make_item(id=2, part_number=" pn-dup ", revision=" a "),
            ]
        )
        result = await use_case.execute(self.actor, [make_row(part_number="PN-DUP", revision="A")])
        out = result.results[0]
        assert out.row_status == "ambiguous"
        assert out.matched_item is None
        assert out.match_source is None
        assert any("Multiple catalogue items share part number" in e for e in out.errors)
        assert not result.all_valid

    async def test_deleted_items_are_never_matched(self):
        use_case = self._use_case([make_item(part_number="PN-1", revision="A", archived=True)])
        result = await use_case.execute(self.actor, [make_row(part_number="PN-1", revision="A")])
        assert result.results[0].row_status == "not_found"

    async def test_no_fallback_lookup(self):
        """Made items have no second natural key: a part-number-only match
        with a non-matching revision is not_found, never narrowed."""
        use_case = self._use_case([make_item(part_number="PN-100", revision="Z")])
        result = await use_case.execute(self.actor, [make_row(part_number="PN-100", revision="A")])
        assert result.results[0].row_status == "not_found"

    # -- project resolution ---------------------------------------------

    async def test_missing_project_is_unresolved_reference_even_when_item_matches(self):
        use_case = self._use_case([make_item()])
        row = make_row(project_number="MISSING-PROJECT")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "unresolved_reference"
        assert out.matched_item is not None
        assert any("MISSING-PROJECT" in e for e in out.errors)
        assert not result.all_valid

    async def test_ambiguous_item_and_missing_project_is_unresolved_reference_not_ambiguous(self):
        """Precedence: invalid > unresolved_reference > ambiguous > not_found > matched."""
        use_case = self._use_case(
            [
                make_item(id=1, part_number="PN-DUP", revision="A"),
                make_item(id=2, part_number=" pn-dup ", revision=" a "),
            ]
        )
        row = make_row(part_number="PN-DUP", revision="A", project_number="MISSING-PROJECT")
        result = await use_case.execute(self.actor, [row])
        assert result.results[0].row_status == "unresolved_reference"

    async def test_resolved_project_id_populated_even_on_not_found_row(self):
        use_case = self._use_case([])
        row = make_row()
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "not_found"
        assert out.resolved_project_id == 1

    # -- invalid rows -----------------------------------------------------

    async def test_invalid_row_for_non_positive_quantity(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(quantity=0)])
        row = result.results[0]
        assert row.row_status == "invalid"
        assert any("Quantity" in e for e in row.errors)

    async def test_invalid_row_for_missing_project_number(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(project_number=None)])
        assert result.results[0].row_status == "invalid"

    async def test_invalid_row_for_missing_part_number(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(part_number=None)])
        row = result.results[0]
        assert row.row_status == "invalid"
        assert any("Part number" in e for e in row.errors)

    async def test_invalid_row_for_missing_revision(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(revision=None)])
        row = result.results[0]
        assert row.row_status == "invalid"
        assert any("Revision is required." in e for e in row.errors)

    async def test_invalid_row_for_blank_revision(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(revision="   ")])
        assert result.results[0].row_status == "invalid"

    async def test_article_name_never_required(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(article_name=None)])
        assert result.results[0].row_status == "matched"

    # -- divergences (warnings only) --------------------------------------

    async def test_article_name_divergence_reported(self):
        use_case = self._use_case([make_item(article_name="Old Name")])
        row = make_row(article_name="New Name")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "matched"
        div = next(d for d in out.divergences if d.field == "article_name")
        assert div.db_value == "Old Name"
        assert div.file_value == "New Name"

    async def test_no_article_name_divergence_when_file_value_blank(self):
        use_case = self._use_case([make_item(article_name="Old Name")])
        result = await use_case.execute(self.actor, [make_row(article_name=None)])
        fields = {d.field for d in result.results[0].divergences}
        assert "article_name" not in fields

    async def test_inactive_item_refuses_the_row(self):
        # A demand may only name an active item, so the row cannot be committed.
        use_case = self._use_case([make_item(status=MadeItemCatalogueStatus.INACTIVE)])
        result = await use_case.execute(self.actor, [make_row()])
        out = result.results[0]
        assert out.row_status == "invalid"
        assert any("is inactive" in error for error in out.errors)
        assert not result.all_valid

    async def test_replaced_item_refuses_the_row(self):
        use_case = self._use_case([make_item(status=MadeItemCatalogueStatus.REPLACED)])
        result = await use_case.execute(self.actor, [make_row()])
        out = result.results[0]
        assert out.row_status == "invalid"
        assert any("is replaced" in error for error in out.errors)

    async def test_active_status_has_no_status_divergence(self):
        use_case = self._use_case([make_item(status=MadeItemCatalogueStatus.ACTIVE)])
        result = await use_case.execute(self.actor, [make_row()])
        fields = {d.field for d in result.results[0].divergences}
        assert "status" not in fields

    # -- misc ---------------------------------------------------------------

    async def test_all_valid_false_when_any_row_is_not_matched(self):
        use_case = self._use_case([make_item()])
        rows = [make_row(row_index=0), make_row(row_index=1, revision="NOPE")]
        result = await use_case.execute(self.actor, rows)
        assert not result.all_valid

    async def test_insufficient_permission_raises(self):
        from src.modules.platform.domain.exceptions import InsufficientPermissionsError

        actor = make_user(permissions=[])
        use_case = self._use_case([make_item()])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, [make_row()])

    async def test_no_write_made_items_needed(self):
        """WRITE_DEMAND_ITEMS alone is sufficient; WRITE_MADE_ITEMS is
        deliberately absent from setup_method's permissions and must not be
        required."""
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row()])
        assert result.results[0].row_status == "matched"


# ── CommitBatchMadeItemDemandRows ────────────────────────────────────


class TestCommitBatchMadeItemDemandRows:
    def setup_method(self):
        # Deliberately no WRITE_MADE_ITEMS: the batch importer never
        # touches the catalogue, only WRITE_DEMAND_ITEMS is required.
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.project_repo = FakeProjectRepo([make_project()])
        self.session = FakeSession()
        self.event_bus = FakeEventBus()

    def _use_case(self, items: list[MadeItem] | None = None) -> CommitBatchMadeItemDemandRows:
        self.item_repo = FakeMadeItemRepo(items)
        self.demand_repo = FakeDemandRepo()
        return CommitBatchMadeItemDemandRows(
            demand_repo=self.demand_repo,
            item_repo=self.item_repo,
            project_repo=self.project_repo,
            uow=self.session,
            event_bus=self.event_bus,
            reconciler=demand_reconciler(),
        )

    async def test_commit_matched_row_creates_demand_with_pcs_unit_and_defaults(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row()])
        assert len(result.created_demand_ids) == 1
        assert self.session.committed
        (demand,) = self.demand_repo._demands.values()
        assert demand.unit == "PCS"
        assert demand.items_per_unit == 1.0
        assert demand.high_priority is False
        assert demand.notify_on_delivery is False
        assert demand.is_alteration is False
        assert demand.alteration_of_made_item_id is None
        assert demand.status == "open"
        # Never creates or updates a MadeItem.
        assert self.item_repo.save_calls == []

    async def test_commit_does_not_require_write_made_items(self):
        # setup_method already omits WRITE_MADE_ITEMS; this asserts commit
        # still succeeds.
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row()])
        assert len(result.created_demand_ids) == 1

    async def test_commit_refuses_not_found_row_and_rolls_back(self):
        use_case = self._use_case([])
        row = make_row()
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, [row])
        assert self.session.rolled_back
        assert not self.session.committed
        assert self.item_repo.save_calls == []
        assert self.event_bus.published == []

    async def test_commit_refuses_ambiguous_row_and_rolls_back(self):
        use_case = self._use_case(
            [
                make_item(id=1, part_number="PN-DUP", revision="A"),
                make_item(id=2, part_number=" pn-dup ", revision=" a "),
            ]
        )
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, [make_row(part_number="PN-DUP", revision="A")])
        assert self.session.rolled_back
        assert not self.session.committed
        assert self.event_bus.published == []

    async def test_commit_refuses_unresolved_reference_row_and_rolls_back(self):
        use_case = self._use_case([make_item()])
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, [make_row(project_number="MISSING")])
        assert self.session.rolled_back
        assert not self.session.committed
        assert self.event_bus.published == []

    async def test_commit_aborts_whole_batch_on_unresolvable_row(self):
        use_case = self._use_case([make_item()])
        rows = [make_row(row_index=0), make_row(row_index=1, project_number="MISSING")]
        with pytest.raises(BatchDemandRowInvalidError, match=r"^Row 1 "):
            await use_case.execute(self.actor, rows)
        # all-or-nothing: nothing should have been committed for row 0 either
        assert self.session.rolled_back
        assert not self.session.committed
        assert self.event_bus.published == []

    async def test_empty_delivery_date_falls_back_to_project_default(self):
        self.project_repo = FakeProjectRepo(
            [make_project(required_delivery_date_made=date(2026, 9, 1))]
        )
        use_case = self._use_case([make_item()])
        await use_case.execute(self.actor, [make_row()])
        (demand,) = self.demand_repo._demands.values()
        assert demand.desired_delivery_date == date(2026, 9, 1)

    async def test_row_delivery_date_wins_over_project_default(self):
        self.project_repo = FakeProjectRepo(
            [make_project(required_delivery_date_made=date(2026, 9, 1))]
        )
        use_case = self._use_case([make_item()])
        await use_case.execute(self.actor, [make_row(desired_delivery_date=date(2026, 12, 25))])
        (demand,) = self.demand_repo._demands.values()
        assert demand.desired_delivery_date == date(2026, 12, 25)

    async def test_commit_publishes_one_event_per_created_demand(self):
        use_case = self._use_case([make_item(id=1), make_item(id=2, part_number="PN-200")])
        rows = [
            make_row(row_index=0),
            make_row(row_index=1, part_number="PN-200", article_name="Bracket"),
        ]
        result = await use_case.execute(self.actor, rows)
        assert len(self.event_bus.published) == 2
        for event in self.event_bus.published:
            assert isinstance(event, MadeItemDemandItemCreated)
        published_demand_ids = {event.demand_id for event in self.event_bus.published}
        assert published_demand_ids == set(result.created_demand_ids)
        published_made_item_ids = {event.made_item_id for event in self.event_bus.published}
        assert published_made_item_ids == {1, 2}

    async def test_commit_publishes_no_events_on_rollback(self):
        use_case = self._use_case([make_item()])
        rows = [make_row(row_index=0), make_row(row_index=1, revision="MISSING")]
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, rows)
        assert self.event_bus.published == []
