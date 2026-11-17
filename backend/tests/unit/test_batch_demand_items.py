"""
Unit tests for batch demand import (Excel) validate/commit use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.

This is a lookup-only importer: rows only ever create BoughtItemDemandItem
rows against catalogue items that already exist. It never creates or
updates a BoughtItem. See src/modules/catalogue/application/use_cases/bought_item/
batch_demand_items.py for the resolution rules these tests pin down.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.events.bought_item_events import DemandItemCreated
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.fulfillment.application.dto.bought_item_demand_dto import BatchDemandRowInput
from src.modules.fulfillment.application.use_cases.bought_item_demand.batch_demand_items import (
    CommitBatchDemandRows,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.batch_demand_items import (
    ValidateBatchDemandRows,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.errors import BatchDemandRowInvalidError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler

# ── Helpers ───────────────────────────────────────────────────────────


def make_row(**overrides) -> BatchDemandRowInput:
    """Default row resolves via the order-code + manufacturer fallback key
    (no part number) against `make_item()`'s defaults."""
    defaults = dict(
        row_index=0,
        project_number="P0001",
        quantity=10.0,
        unit="pcs",
        part_number=None,
        article_name="Hex Bolt M8",
        order_code="ORD-1",
        manufacturer_name="Acme Supplier",
    )
    defaults.update(overrides)
    return BatchDemandRowInput(**defaults)


def make_item(
    id: int = 1,
    order_code_1: str = "ORD-1",
    order_code_2: str | None = None,
    article_name: str = "Hex Bolt M8",
    part_number: str | None = None,
    manufacturer_id: int = 1,
    manufacturer_name: str = "Acme Supplier",
    archived: bool = False,
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        article_name=article_name,
        order_code_1=order_code_1,
        order_code_2=order_code_2,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.WEB,
        part_number=part_number,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=manufacturer_id,
        article_group_ids=[],
        successor_item_id=None,
        manufacturer_name=manufacturer_name,
        article_groups=[],
    )


def make_project(
    id: int = 1,
    project_number: str = "P0001",
    required_delivery_date_bought: date | None = None,
) -> Project:
    return Project(
        id=id,
        created=datetime.now(UTC),
        project_number=project_number,
        required_delivery_date_bought=required_delivery_date_bought,
    )


def make_supplier(id: int = 1, name: str = "Acme Supplier") -> Supplier:
    return Supplier(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        legal_name=None,
        vat_id=None,
        level=SupplierLevel.B,
        capability_ids=[],
        article_group_ids=[],
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        order_email=None,
        order_language=None,
        order_template=None,
        request_email=None,
        request_language=None,
        request_template=None,
        creator_id=1,
    )


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeBoughtItemRepo:
    """Mirrors the real SQL repo's semantics closely enough for these tests:
    part_number / order_code_1 are substring-prefiltered (real repo uses
    ILIKE '%term%'), manufacturer_id is exact, deleted items are always
    excluded. _RowResolver then narrows to a normalized-exact match itself,
    same as the real repo's callers do today."""

    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: list[BoughtItem] = list(items or [])
        self.save_calls: list[BoughtItem] = []

    async def get_multi(self, filters: BoughtItemFilterDto):
        results = [i for i in self._items if not i.archived]
        if filters.part_number:
            term = filters.part_number.lower()
            results = [i for i in results if i.part_number and term in i.part_number.lower()]
        if filters.order_code_1:
            term = filters.order_code_1.lower()
            results = [i for i in results if term in i.order_code_1.lower()]
        if filters.manufacturer_id is not None:
            results = [i for i in results if i.manufacturer_id == filters.manufacturer_id]
        return len(results), results

    async def save(self, item: BoughtItem) -> BoughtItem:
        # The batch importer must never create or update a BoughtItem; tests
        # assert `save_calls` stays empty rather than relying on this never
        # being wired up.
        self.save_calls.append(item)
        return item


class FakeDemandRepo:
    def __init__(self):
        self._demands: dict[int, BoughtItemDemandItem] = {}
        self._next_id = 1

    @property
    def demands(self) -> dict[int, BoughtItemDemandItem]:
        """The stored demands by id, for assertions."""
        return self._demands

    async def save(self, demand: BoughtItemDemandItem) -> BoughtItemDemandItem:
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


class FakeSupplierRepo:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers = list(suppliers or [])

    async def get_multi(self, filters: SupplierFilterDto):
        results = self._suppliers
        if filters.name:
            term = filters.name.lower()
            results = [s for s in results if term in s.name.lower()]
        return len(results), results


class FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeEventBus:
    def __init__(self):
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


# ── ValidateBatchDemandRows ──────────────────────────────────────────


class TestValidateBatchDemandRows:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.project_repo = FakeProjectRepo([make_project()])
        self.supplier_repo = FakeSupplierRepo([make_supplier()])

    def _use_case(self, items: list[BoughtItem] | None = None) -> ValidateBatchDemandRows:
        self.item_repo = FakeBoughtItemRepo(items)
        return ValidateBatchDemandRows(
            item_repo=self.item_repo,
            project_repo=self.project_repo,
            supplier_repo=self.supplier_repo,
        )

    # -- part number match --------------------------------------------

    async def test_part_number_exact_match_case_and_whitespace_insensitive(self):
        use_case = self._use_case([make_item(part_number="PN-100")])
        result = await use_case.execute(
            self.actor, [make_row(part_number="  pn-100  ", article_name="Hex Bolt M8")]
        )
        row = result.results[0]
        assert row.row_status == "matched"
        assert row.match_source == "part_number"
        assert row.matched_item.id == 1
        assert row.divergences == []
        assert result.all_valid

    async def test_ambiguous_part_number_blocks_with_no_narrowing(self):
        use_case = self._use_case(
            [
                make_item(id=1, part_number="PN-200", order_code_1="ORD-A"),
                make_item(id=2, part_number=" pn-200 ", order_code_1="ORD-B"),
            ]
        )
        # Row also carries a valid fallback key that *would* resolve to item 1
        # alone; it must not be used to narrow the ambiguous part-number hit.
        row = make_row(part_number="PN-200", order_code="ORD-A", manufacturer_name="Acme Supplier")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "ambiguous"
        assert out.matched_item is None
        assert out.match_source is None
        assert any("Multiple catalogue items share part number" in e for e in out.errors)
        assert not result.all_valid

    async def test_part_number_not_found_falls_back_and_warns_of_divergence(self):
        use_case = self._use_case(
            [make_item(part_number="PN-999", order_code_1="ORD-2", article_name="Widget")]
        )
        row = make_row(
            part_number="PN-DOES-NOT-EXIST",
            order_code="ORD-2",
            manufacturer_name="Acme Supplier",
            article_name="Widget",
        )
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "matched"
        assert out.match_source == "order_code_manufacturer"
        assert len(out.divergences) == 1
        div = out.divergences[0]
        assert div.field == "part_number"
        assert div.db_value == "PN-999"
        assert div.file_value == "PN-DOES-NOT-EXIST"

    async def test_part_number_divergence_reports_none_db_value_when_item_has_no_part_number(self):
        use_case = self._use_case(
            [make_item(part_number=None, order_code_1="ORD-3", article_name="Widget")]
        )
        row = make_row(
            part_number="PN-ABC",
            order_code="ORD-3",
            manufacturer_name="Acme Supplier",
            article_name="Widget",
        )
        result = await use_case.execute(self.actor, [row])
        div = result.results[0].divergences[0]
        assert div.field == "part_number"
        assert div.db_value is None
        assert div.file_value == "PN-ABC"

    async def test_part_number_not_found_and_no_fallback_key_is_not_found(self):
        use_case = self._use_case([make_item(part_number="PN-999")])
        row = make_row(part_number="UNKNOWN-PN", order_code=None, manufacturer_name=None)
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "not_found"
        assert out.matched_item is None
        assert not result.all_valid

    async def test_deleted_items_are_never_matched(self):
        use_case = self._use_case(
            [make_item(part_number="PN-1", order_code_1="ORD-1", archived=True)]
        )
        row = make_row(part_number="PN-1", order_code="ORD-1", manufacturer_name="Acme Supplier")
        result = await use_case.execute(self.actor, [row])
        # Deleted item is invisible to both the part-number path and the
        # order-code + manufacturer fallback.
        assert result.results[0].row_status == "not_found"

    # -- order code + manufacturer fallback ----------------------------

    async def test_fallback_match_by_order_code_and_manufacturer(self):
        use_case = self._use_case([make_item()])
        row = make_row(part_number=None, order_code="ORD-1", manufacturer_name="Acme Supplier")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "matched"
        assert out.match_source == "order_code_manufacturer"
        assert out.matched_item.id == 1

    async def test_same_order_code_different_manufacturer_is_not_found(self):
        self.supplier_repo = FakeSupplierRepo(
            [make_supplier(id=1, name="Acme Supplier"), make_supplier(id=2, name="Globex")]
        )
        use_case = self._use_case(
            [make_item(order_code_1="ORD-1", manufacturer_id=1, manufacturer_name="Acme Supplier")]
        )
        row = make_row(part_number=None, order_code="ORD-1", manufacturer_name="Globex")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "not_found"
        assert any("No catalogue item found for order code" in e for e in out.errors)

    async def test_unknown_manufacturer_is_not_found(self):
        use_case = self._use_case([make_item()])
        row = make_row(part_number=None, order_code="ORD-1", manufacturer_name="Nonexistent Co")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "not_found"
        assert any("Manufacturer" in e and "not found" in e for e in out.errors)

    async def test_order_code_2_is_never_matched(self):
        use_case = self._use_case(
            [make_item(order_code_1="ORD-PRIMARY", order_code_2="ORD-SECRET")]
        )
        row = make_row(part_number=None, order_code="ORD-SECRET", manufacturer_name="Acme Supplier")
        result = await use_case.execute(self.actor, [row])
        assert result.results[0].row_status == "not_found"

    # -- project resolution ---------------------------------------------

    async def test_missing_project_is_unresolved_reference_even_when_item_matches(self):
        use_case = self._use_case([make_item(part_number="PN-1")])
        row = make_row(part_number="PN-1", project_number="MISSING-PROJECT")
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
                make_item(id=1, part_number="PN-DUP"),
                make_item(id=2, part_number=" pn-dup "),
            ]
        )
        row = make_row(part_number="PN-DUP", project_number="MISSING-PROJECT")
        result = await use_case.execute(self.actor, [row])
        assert result.results[0].row_status == "unresolved_reference"

    async def test_resolved_project_id_populated_even_on_not_found_row(self):
        use_case = self._use_case([])
        row = make_row(part_number=None, order_code="UNKNOWN", manufacturer_name="Unknown Co")
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

    async def test_invalid_row_for_missing_unit(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(unit=None)])
        assert result.results[0].row_status == "invalid"

    async def test_invalid_row_for_missing_project_number(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(project_number=None)])
        assert result.results[0].row_status == "invalid"

    async def test_invalid_row_for_missing_lookup_key(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(
            self.actor, [make_row(part_number=None, order_code=None, manufacturer_name=None)]
        )
        assert result.results[0].row_status == "invalid"

    async def test_invalid_row_for_order_code_without_manufacturer(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(
            self.actor, [make_row(part_number=None, order_code="ORD-1", manufacturer_name=None)]
        )
        assert result.results[0].row_status == "invalid"

    async def test_article_name_never_required(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row(part_number=None, article_name=None)])
        assert result.results[0].row_status == "matched"

    # -- divergences ------------------------------------------------------

    async def test_article_name_divergence_reported_for_part_number_match(self):
        use_case = self._use_case([make_item(part_number="PN-1", article_name="Old Name")])
        row = make_row(part_number="PN-1", article_name="New Name")
        result = await use_case.execute(self.actor, [row])
        out = result.results[0]
        assert out.row_status == "matched"
        assert any(d.field == "article_name" for d in out.divergences)

    async def test_manufacturer_and_order_code_divergence_only_for_part_number_match(self):
        use_case = self._use_case(
            [
                make_item(
                    part_number="PN-1",
                    order_code_1="DB-ORDER-CODE",
                    manufacturer_id=1,
                    manufacturer_name="Acme Supplier",
                )
            ]
        )
        row = make_row(
            part_number="PN-1", order_code="FILE-ORDER-CODE", manufacturer_name="Other Mfg"
        )
        result = await use_case.execute(self.actor, [row])
        fields = {d.field for d in result.results[0].divergences}
        assert fields == {"manufacturer_name", "order_code"}

    async def test_no_manufacturer_or_order_code_divergence_for_fallback_match(self):
        use_case = self._use_case([make_item(article_name="Old Name")])
        row = make_row(
            part_number=None,
            order_code="ORD-1",
            manufacturer_name="Acme Supplier",
            article_name="New Name",
        )
        result = await use_case.execute(self.actor, [row])
        fields = {d.field for d in result.results[0].divergences}
        assert fields == {"article_name"}

    async def test_no_part_number_divergence_for_part_number_match(self):
        use_case = self._use_case([make_item(part_number="PN-1")])
        row = make_row(part_number="PN-1")
        result = await use_case.execute(self.actor, [row])
        fields = {d.field for d in result.results[0].divergences}
        assert "part_number" not in fields

    # -- misc ---------------------------------------------------------------

    async def test_all_valid_false_when_any_row_is_not_matched(self):
        use_case = self._use_case([make_item()])
        rows = [make_row(row_index=0), make_row(row_index=1, order_code="MISSING")]
        result = await use_case.execute(self.actor, rows)
        assert not result.all_valid

    async def test_insufficient_permission_raises(self):
        from src.modules.platform.domain.exceptions import InsufficientPermissionsError

        actor = make_user(permissions=[])
        use_case = self._use_case([make_item()])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, [make_row()])


# ── CommitBatchDemandRows ────────────────────────────────────────────


class TestCommitBatchDemandRows:
    def setup_method(self):
        # Deliberately no WRITE_BOUGHT_ITEMS: the batch importer never
        # touches the catalogue, only WRITE_DEMAND_ITEMS is required.
        self.actor = make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])
        self.project_repo = FakeProjectRepo([make_project()])
        self.supplier_repo = FakeSupplierRepo([make_supplier()])
        self.session = FakeSession()
        self.event_bus = FakeEventBus()

    def _use_case(self, items: list[BoughtItem] | None = None) -> CommitBatchDemandRows:
        self.item_repo = FakeBoughtItemRepo(items)
        self.demand_repo = FakeDemandRepo()
        return CommitBatchDemandRows(
            demand_repo=self.demand_repo,
            item_repo=self.item_repo,
            project_repo=self.project_repo,
            supplier_repo=self.supplier_repo,
            uow=self.session,
            event_bus=self.event_bus,
            reconciler=demand_reconciler(),
        )

    async def test_commit_matched_row_creates_demand_only(self):
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row()])
        assert len(result.created_demand_ids) == 1
        assert self.session.committed
        # Never creates or updates a BoughtItem.
        assert self.item_repo.save_calls == []

    async def test_commit_does_not_require_write_bought_items(self):
        # setup_method already omits WRITE_BOUGHT_ITEMS; this asserts commit
        # still succeeds.
        use_case = self._use_case([make_item()])
        result = await use_case.execute(self.actor, [make_row()])
        assert len(result.created_demand_ids) == 1

    async def test_commit_refuses_not_found_row_and_rolls_back(self):
        use_case = self._use_case([])
        row = make_row(part_number=None, order_code="MISSING", manufacturer_name="Acme Supplier")
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, [row])
        assert self.session.rolled_back
        assert not self.session.committed
        assert self.item_repo.save_calls == []
        assert self.event_bus.published == []

    async def test_commit_refuses_ambiguous_row_and_rolls_back(self):
        use_case = self._use_case(
            [
                make_item(id=1, part_number="PN-DUP"),
                make_item(id=2, part_number=" pn-dup "),
            ]
        )
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, [make_row(part_number="PN-DUP")])
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
            [make_project(required_delivery_date_bought=date(2026, 9, 1))]
        )
        use_case = self._use_case([make_item()])
        await use_case.execute(self.actor, [make_row()])
        (demand,) = self.demand_repo._demands.values()
        assert demand.desired_delivery_date == date(2026, 9, 1)

    async def test_row_delivery_date_wins_over_project_default(self):
        self.project_repo = FakeProjectRepo(
            [make_project(required_delivery_date_bought=date(2026, 9, 1))]
        )
        use_case = self._use_case([make_item()])
        await use_case.execute(self.actor, [make_row(desired_delivery_date=date(2026, 12, 25))])
        (demand,) = self.demand_repo._demands.values()
        assert demand.desired_delivery_date == date(2026, 12, 25)

    async def test_commit_publishes_one_event_per_created_demand(self):
        use_case = self._use_case(
            [make_item(id=1), make_item(id=2, order_code_1="ORD-2", part_number="PN-2")]
        )
        rows = [
            make_row(row_index=0),
            make_row(row_index=1, part_number="PN-2", order_code=None, manufacturer_name=None),
        ]
        result = await use_case.execute(self.actor, rows)
        assert len(self.event_bus.published) == 2
        for event in self.event_bus.published:
            assert isinstance(event, DemandItemCreated)
        published_demand_ids = {event.demand_id for event in self.event_bus.published}
        assert published_demand_ids == set(result.created_demand_ids)
        published_item_ids = {event.item_id for event in self.event_bus.published}
        assert published_item_ids == {1, 2}

    async def test_commit_publishes_no_events_on_rollback(self):
        use_case = self._use_case([make_item()])
        rows = [make_row(row_index=0), make_row(row_index=1, project_number="MISSING")]
        with pytest.raises(BatchDemandRowInvalidError):
            await use_case.execute(self.actor, rows)
        assert self.event_bus.published == []
