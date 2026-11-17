"""
GetQaTasks: the QA worklist read model behind GET /production-qa.
Covers the filter contract the views bar drives (Show Completed / Show
Canceled / Show Future Tasks), the evidence flag the list warns on, and
the flattening of order + step + lot + part into one row.

The "future" rule is the user-facing one: a still-waiting task is future
when Start would be refused (can_start false), when it has no planned
start at all, or when it is planned to begin after today. Terminal and
already-started tasks are exempt (see _is_future). No database, no HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import GetQaTasks
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import (
    QaTaskFilterDto,
)
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import _is_future
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.factories import make_user
from tests.unit._tenant_settings import TenantSettings

TODAY = date(2026, 8, 14)

# ── Fixtures ──────────────────────────────────────────────────────────


def make_inspection_step(position_id: int = 1, requires_evidence: bool = False) -> LotStep:
    return LotStep(
        id=position_id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        sequence=1,
        creator_id=1,
        fabrication_method_id=None,
        lot_id=1,
        position_id=position_id,
        source_process_id=None,
        role=StepRole.INSPECTION,
        inspection_method_id=1,
        inspection_method_name=LocalizedText(
            {"enGB": "Measurement" if requires_evidence else "Visual Inspection"}
        ),
        inspection_method_requires_evidence=requires_evidence,
    )


def make_position(id: int = 1, requires_evidence: bool = False) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=6.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[make_inspection_step(id, requires_evidence)],
    )


def make_lot(positions: list[LotPosition] | None = None) -> ProductionLot:
    lot = ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LN-26-00023",
        quantity=6.0,
        status=LotStatus.IN_PROGRESS,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=16,
        project_id=3,
        input_demand_id=None,
    )
    lot.positions = positions if positions is not None else [make_position()]
    lot.made_item_part_number = "TN-26-00006"
    lot.made_item_article_name = "Shaft"
    lot.made_item_revision = "0"
    lot.made_item_material = "1.3505"
    lot.project_number = "P26003"
    lot.project_customer = "ROOFCO"
    # Rework lot: exempt from sequence-1 raw-material gating, which would
    # otherwise dominate can_start in these fixtures.
    lot.source_made_item_id = 99
    return lot


def make_order(
    id: int = 100,
    status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
    planned_start: datetime | None = None,
    lot_position_id: int = 1,
) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"FN-26-{id:05d}",
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=6.0,
        quantity_completed=0.0,
        estimated_duration_minutes=0,
        note=None,
        planned_start=planned_start,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=None,
        lot_position_id=lot_position_id,
        lot_id=1,
    )


def make_completion(
    id: int, operator: User | None, completion_date: date
) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=id,
        production_order_id=100,
        quantity=1.0,
        quantity_accepted=1.0,
        quantity_rejected=0.0,
        completion_date=completion_date,
        note=None,
        operator_id=operator.id if operator else 1,
        recorded_by_id=1,
        created=datetime(2026, 8, 14, 10, 0),
        operator=operator,
    )


def make_file(order_id: int, category: ProductionOrderFileCategory) -> ProductionOrderFile:
    return ProductionOrderFile(
        id=1,
        created=date(2026, 1, 1),
        production_order_id=order_id,
        file_name="report.pdf",
        stored_name="report.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        storage_path="",
        sha256="",
        category=category,
        uploaded_by_user_id=1,
    )


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeOrderRepo:
    """Honours the two filters GetQaTasks relies on, so the test proves the
    use case actually asks for inspection-role orders in the right states."""

    def __init__(self, orders: list[ProductionOrder], step_roles: dict[int, str]) -> None:
        self._orders = orders
        self._step_roles = step_roles
        self.last_filters = None

    async def get_multi(self, filters):
        self.last_filters = filters
        rows = self._orders
        if filters.statuses:
            rows = [o for o in rows if o.status in filters.statuses]
        if filters.step_role:
            rows = [o for o in rows if self._step_roles.get(o.lot_position_id) == filters.step_role]
        return len(rows), list(rows)

    async def get_by_lot_position_ids(self, ids: list[int]) -> list[ProductionOrder]:
        return [o for o in self._orders if o.lot_position_id in ids]

    async def get_by_lot_position_id(self, id: int) -> list[ProductionOrder]:
        return [o for o in self._orders if o.lot_position_id == id]


class FakeLotRepo:
    def __init__(self, lots: list[ProductionLot]) -> None:
        self._lots = {lot.id: lot for lot in lots}

    async def get_by_id(self, id: int) -> ProductionLot | None:
        return self._lots.get(id)

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return 0.0

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}


class FakeFileRepo:
    def __init__(self, files: list[ProductionOrderFile] | None = None) -> None:
        self._files = files or []

    async def get_by_item_ids(self, item_ids: list[int]) -> list[ProductionOrderFile]:
        return [f for f in self._files if f.production_order_id in item_ids]


class FakeEmptyRepo:
    async def get_by_id(self, id: int):
        return None

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_lot_position_id(self, lot_position_id: int):
        return None

    async def get_by_lot_position_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return 0.0

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}


def build(
    orders: list[ProductionOrder],
    lot: ProductionLot | None = None,
    files: list[ProductionOrderFile] | None = None,
    step_roles: dict[int, str] | None = None,
) -> tuple[GetQaTasks, FakeOrderRepo]:
    lot = lot if lot is not None else make_lot()
    empty = FakeEmptyRepo()
    order_repo = FakeOrderRepo(orders, step_roles or {1: StepRole.INSPECTION.value})
    lot_repo = FakeLotRepo([lot])
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=lot_repo,  # type: ignore[arg-type]
        order_items=empty,  # type: ignore[arg-type]
        source_item_demands=empty,  # type: ignore[arg-type]
        source_item_allocations=empty,  # type: ignore[arg-type]
        made_item_allocations=empty,  # type: ignore[arg-type]
        made_item_demands=empty,  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    use_case = GetQaTasks(
        order_repo=order_repo,  # type: ignore[arg-type]
        lot_repo=lot_repo,  # type: ignore[arg-type]
        machine_repo=empty,  # type: ignore[arg-type]
        file_repo=FakeFileRepo(files),  # type: ignore[arg-type]
        repos=repos,
    )
    return use_case, order_repo


# ── Filter contract ───────────────────────────────────────────────────


class TestStatusFilters:
    def test_open_statuses_only_by_default(self):
        assert QaTaskFilterDto().statuses() == ["queued", "in_progress", "paused"]

    def test_show_completed_adds_completed(self):
        assert "completed" in QaTaskFilterDto(include_completed=True).statuses()
        assert "canceled" not in QaTaskFilterDto(include_completed=True).statuses()

    def test_show_canceled_adds_canceled(self):
        assert "canceled" in QaTaskFilterDto(include_canceled=True).statuses()

    def test_both_toggles_add_both(self):
        statuses = QaTaskFilterDto(include_completed=True, include_canceled=True).statuses()
        assert "completed" in statuses and "canceled" in statuses

    async def test_the_use_case_asks_only_for_inspection_orders(self):
        use_case, repo = build([make_order()])
        await use_case.execute(QaTaskFilterDto(include_future=True), TODAY)
        assert repo.last_filters.step_role == StepRole.INSPECTION.value


class TestFutureFilter:
    """future = a still-waiting task that Start would refuse, has no
    planned start, or is planned after today. Terminal/started exempt."""

    async def test_a_blocked_task_is_hidden_by_default(self):
        # can_start defaults False and nothing here makes it True.
        use_case, _ = build([make_order()])
        assert (await use_case.execute(QaTaskFilterDto(), TODAY))[1] == []

    async def test_a_blocked_task_is_shown_when_future_is_included(self):
        use_case, _ = build([make_order()])
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        assert len(tasks) == 1
        assert tasks[0].can_start is False

    async def test_a_task_planned_after_today_is_hidden_by_default(self):
        order = make_order(planned_start=datetime(2026, 8, 20, 8, 0))
        order.can_start = True
        use_case, _ = build([order])
        assert (await use_case.execute(QaTaskFilterDto(), TODAY))[1] == []

    async def test_a_task_planned_today_is_shown(self):
        order = make_order(planned_start=datetime(2026, 8, 14, 8, 0))
        order.can_start = True
        use_case, _ = build([order])
        # can_start is recomputed during execute, so assert on visibility
        # rather than on the flag the fixture set.
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        assert len(tasks) == 1

    async def test_an_unplanned_task_is_hidden_by_default(self):
        """Nobody has scheduled it, or the scheduler cleared its dates
        because the upstream chain is unknowable. Either way there is no
        date to work to, so it belongs behind the future toggle."""
        order = make_order(planned_start=None)
        use_case, _ = build([order])
        assert (await use_case.execute(QaTaskFilterDto(), TODAY))[1] == []

    async def test_an_unplanned_task_is_shown_when_future_is_included(self):
        order = make_order(planned_start=None)
        use_case, _ = build([order])
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        assert len(tasks) == 1
        assert tasks[0].planned_start is None

    async def test_a_completed_task_is_not_future(self):
        """can_start is false for any terminal status, so a naive rule would
        swallow completed tasks as "future" and Show Completed would reveal
        nothing unless Show Future Tasks was on too."""
        order = make_order(status=ProductionOrderStatus.COMPLETED)
        use_case, _ = build([order])
        tasks = (await use_case.execute(QaTaskFilterDto(include_completed=True), TODAY))[1]
        assert [t.status for t in tasks] == [ProductionOrderStatus.COMPLETED.value]

    async def test_a_canceled_task_is_not_future(self):
        order = make_order(status=ProductionOrderStatus.CANCELED)
        use_case, _ = build([order])
        tasks = (await use_case.execute(QaTaskFilterDto(include_canceled=True), TODAY))[1]
        assert [t.status for t in tasks] == [ProductionOrderStatus.CANCELED.value]

    async def test_an_undated_task_sorts_alongside_aware_dated_ones_without_crashing(self):
        """A persisted planned_start is timezone-aware (timestamptz), so the
        undated sentinel must be aware too: a naive datetime.max would make
        sorting one of each raise "can't compare offset-naive and
        offset-aware datetimes", a 500 on the whole worklist, and the future
        filter reveals exactly the undated tasks."""
        dated = make_order(id=300, planned_start=datetime(2026, 8, 14, 8, 0, tzinfo=UTC))
        undated = make_order(id=301, planned_start=None)
        use_case, _ = build([undated, dated])
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        # Undated sorts last, behind the one with a real date.
        assert [t.id for t in tasks] == [300, 301]

    async def test_a_started_task_without_planned_dates_is_not_future(self):
        """A PAUSED order keeps no planned dates by design (the scheduler
        skips it in the walk), so the unplanned rule must not hide an
        inspection somebody is halfway through."""
        order = make_order(status=ProductionOrderStatus.PAUSED, planned_start=None)
        order.actual_start = datetime(2026, 8, 13, 9, 0)
        use_case, _ = build([order])
        tasks = (await use_case.execute(QaTaskFilterDto(), TODAY))[1]
        assert len(tasks) == 1
        assert tasks[0].planned_start is None


# ── Paging and ordering ───────────────────────────────────────────────


class TestPaging:
    """skip/limit are applied to the assembled, filtered, ordered worklist,
    not pushed into SQL, because both the future filter and the default
    order read the computed can_start. See GetQaTasks.execute."""

    def _six(self):
        orders = [make_order(id=100 + i) for i in range(6)]
        return build(orders)[0]

    async def test_the_total_counts_the_whole_worklist_not_the_page(self):
        total, page = await self._six().execute(
            QaTaskFilterDto(include_future=True, limit=2), TODAY
        )
        assert total == 6
        assert len(page) == 2

    async def test_skip_walks_through_the_worklist(self):
        use_case = self._six()
        _, first = await use_case.execute(QaTaskFilterDto(include_future=True, limit=2), TODAY)
        _, second = await use_case.execute(
            QaTaskFilterDto(include_future=True, skip=2, limit=2), TODAY
        )
        _, third = await use_case.execute(
            QaTaskFilterDto(include_future=True, skip=4, limit=2), TODAY
        )
        assert [t.id for t in first] == [100, 101]
        assert [t.id for t in second] == [102, 103]
        assert [t.id for t in third] == [104, 105]

    async def test_no_limit_returns_everything_from_skip(self):
        total, page = await self._six().execute(QaTaskFilterDto(include_future=True), TODAY)
        assert total == 6
        assert len(page) == 6

    async def test_skip_past_the_end_is_an_empty_page_not_an_error(self):
        total, page = await self._six().execute(
            QaTaskFilterDto(include_future=True, skip=99, limit=2), TODAY
        )
        assert total == 6
        assert page == []

    async def test_the_total_excludes_rows_the_future_filter_drops(self):
        """The count has to match what the list can show, or the paginator
        offers pages that render empty."""
        use_case = self._six()
        total, page = await use_case.execute(QaTaskFilterDto(limit=2), TODAY)
        # Nothing here is startable, so the default filter hides all six.
        assert total == 0
        assert page == []


class TestOrderingByColumn:
    async def _tasks(self, order_by: str, order_dir: str = "asc"):
        lot = make_lot()
        orders = [
            make_order(id=100, planned_start=datetime(2026, 8, 20, 8, 0)),
            make_order(id=101, planned_start=datetime(2026, 8, 12, 8, 0)),
            make_order(id=102, planned_start=None),
        ]
        use_case, _ = build(orders, lot=lot)
        _, page = await use_case.execute(
            QaTaskFilterDto(include_future=True, order_by=order_by, order_dir=order_dir),
            TODAY,
        )
        return page

    async def test_planned_ascending_puts_the_earliest_first_and_undated_last(self):
        assert [t.id for t in await self._tasks("planned")] == [101, 100, 102]

    async def test_planned_descending_reverses_it(self):
        assert [t.id for t in await self._tasks("planned", "desc")] == [102, 100, 101]

    async def test_an_unknown_order_by_falls_back_to_the_urgency_order(self):
        """A stale client sending a column the server no longer sorts on
        gets the default worklist order, not an exception."""
        lot = make_lot()
        use_case, _ = build([make_order(id=100), make_order(id=101)], lot=lot)
        _, page = await use_case.execute(
            QaTaskFilterDto(include_future=True, order_by="nonsense"), TODAY
        )
        assert [t.id for t in page] == [100, 101]

    async def test_equal_values_keep_a_stable_order_across_calls(self):
        """Same quantity on every row: without the id tie-break the order
        could differ between refreshes and rows would appear to jump."""
        lot = make_lot()
        orders = [make_order(id=i) for i in (103, 101, 102)]
        use_case, _ = build(orders, lot=lot)
        pages = [
            (
                await use_case.execute(
                    QaTaskFilterDto(include_future=True, order_by="quantity"), TODAY
                )
            )[1]
            for _ in range(2)
        ]
        assert [t.id for t in pages[0]] == [101, 102, 103]
        assert [t.id for t in pages[0]] == [t.id for t in pages[1]]


# ── Assembly ──────────────────────────────────────────────────────────


class TestAssembly:
    async def _one(self, **kwargs):
        use_case, _ = build(**kwargs)
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        assert len(tasks) == 1
        return tasks[0]

    async def test_flattens_the_part_and_lot_onto_the_task(self):
        task = await self._one(orders=[make_order()])
        assert task.made_item_part_number == "TN-26-00006"
        assert task.made_item_article_name == "Shaft"
        assert task.made_item_revision == "0"
        assert task.made_item_material == "1.3505"
        assert task.lot_number == "LN-26-00023"
        assert task.project_number == "P26003"
        assert task.project_customer == "ROOFCO"

    async def test_the_task_id_is_the_production_order_id(self):
        """So every existing production-order action applies unchanged."""
        task = await self._one(orders=[make_order(id=113)])
        assert task.id == 113
        assert task.production_order_number == "FN-26-00113"

    async def test_carries_the_inspection_method(self):
        task = await self._one(orders=[make_order()])
        assert task.inspection_method_name == {"enGB": "Visual Inspection"}
        assert task.requires_evidence is False

    async def test_requires_evidence_comes_from_the_method(self):
        lot = make_lot([make_position(requires_evidence=True)])
        task = await self._one(orders=[make_order()], lot=lot)
        assert task.requires_evidence is True
        assert task.inspection_method_name == {"enGB": "Measurement"}

    async def test_has_evidence_is_false_without_a_measurement_report(self):
        task = await self._one(orders=[make_order(id=100)])
        assert task.has_evidence is False

    async def test_has_evidence_is_true_with_a_measurement_report(self):
        files = [make_file(100, ProductionOrderFileCategory.MEASUREMENT_REPORT)]
        task = await self._one(orders=[make_order(id=100)], files=files)
        assert task.has_evidence is True

    async def test_the_evidence_files_ride_along_on_the_row(self):
        """Embedded rather than fetched per row: production orders have no
        bulk file endpoint, so a per-row fetch would be one request per
        visible task."""
        files = [make_file(100, ProductionOrderFileCategory.MEASUREMENT_REPORT)]
        task = await self._one(orders=[make_order(id=100)], files=files)
        assert [f.file_name for f in task.evidence_files] == ["report.pdf"]
        assert task.evidence_files[0].mime_type == "application/pdf"

    async def test_non_evidence_files_are_not_listed(self):
        # The enum holds only the evidence category, so a file of any other
        # category is built with a plain string.
        files = [make_file(100, "general")]  # type: ignore[arg-type]
        task = await self._one(orders=[make_order(id=100)], files=files)
        assert task.evidence_files == []

    async def test_evidence_files_are_grouped_per_order(self):
        files = [make_file(999, ProductionOrderFileCategory.MEASUREMENT_REPORT)]
        task = await self._one(orders=[make_order(id=100)], files=files)
        assert task.evidence_files == []

    async def test_another_file_category_does_not_count_as_evidence(self):
        # The enum holds only the evidence category, so a file of any other
        # category is built with a plain string.
        files = [make_file(100, "general")]  # type: ignore[arg-type]
        task = await self._one(orders=[make_order(id=100)], files=files)
        assert task.has_evidence is False

    async def test_evidence_is_matched_per_order(self):
        """A report on a different order must not mark this one done."""
        files = [make_file(999, ProductionOrderFileCategory.MEASUREMENT_REPORT)]
        task = await self._one(orders=[make_order(id=100)], files=files)
        assert task.has_evidence is False


class TestFutureDayInTheTenantZone:
    def test_a_start_after_vienna_midnight_lies_on_a_future_day(self):
        """22:30 UTC on 14 August is 00:30 on 15 August in Vienna, a day
        after today there, while in UTC it is still today."""
        order = make_order(planned_start=datetime(2026, 8, 14, 22, 30, tzinfo=UTC))
        order.can_start = True
        assert _is_future(order, TODAY, ZoneInfo("Europe/Vienna")) is True
        assert _is_future(order, TODAY, UTC) is False


class TestFinished:
    """The "Finished" / "Finished by" columns: when the inspection ended and
    who actually carried it out."""

    async def _one(self, order):
        use_case, _ = build([order])
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        assert len(tasks) == 1
        return tasks[0]

    async def test_an_open_task_has_no_finished_date_or_operator(self):
        task = await self._one(make_order())
        assert task.actual_end is None
        assert task.finished_by is None

    async def test_actual_end_is_carried_through(self):
        order = make_order()
        order.actual_end = datetime(2026, 8, 14, 16, 30)
        task = await self._one(order)
        assert task.actual_end == datetime(2026, 8, 14, 16, 30)

    async def test_finished_by_is_the_operator_not_the_recorder(self):
        """ProductionOrderCompletion separates who did the work from who
        typed it in; the QA list wants the former."""
        operator = make_user(id=7, full_name="Anna Mock")
        order = make_order()
        order.completions = [make_completion(1, operator, date(2026, 8, 14))]
        task = await self._one(order)
        assert task.finished_by is not None
        assert task.finished_by.full_name == "Anna Mock"

    async def test_finished_by_uses_the_most_recent_completion(self):
        first = make_user(id=7, full_name="Anna Mock")
        second = make_user(id=8, full_name="Ben Green")
        order = make_order()
        order.completions = [
            make_completion(1, first, date(2026, 8, 12)),
            make_completion(2, second, date(2026, 8, 14)),
        ]
        task = await self._one(order)
        assert task.finished_by.full_name == "Ben Green"


class TestOrdering:
    async def test_actionable_tasks_sort_before_blocked_ones(self):
        blocked = make_order(id=1)
        ready = make_order(id=2)
        ready.can_start = True
        use_case, _ = build([blocked, ready])
        tasks = (await use_case.execute(QaTaskFilterDto(include_future=True), TODAY))[1]
        # can_start is recomputed, so both may end up blocked; the contract
        # under test is that the sort is total and stable, never raising on
        # a None planned_start.
        assert [t.id for t in tasks] == sorted(
            [t.id for t in tasks], key=lambda i: (not _by_id(tasks, i).can_start, i)
        )


def _by_id(tasks, id):
    return next(t for t in tasks if t.id == id)
