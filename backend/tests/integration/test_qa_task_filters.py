"""
Column filters of the QA worklist. The predicates live in
SqlAlchemyProductionOrderRepository.get_multi, so most tests drive the
repository directly against the throwaway SQLite database with one matching
and one non-matching order per filter. A few HTTP tests pin that the params
bind from the query string (list params from repeated keys) and reach the
repository through GetQaTasks, and that a status pick replaces the
completed and canceled toggles.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

URL = "/api/v1/web/production-qa/"

_seq = itertools.count(1)


async def _make_inspection_method(db, creator_id: int, name: str) -> InspectionMethod:
    saved = await SqlAlchemyInspectionMethodRepository(db).save(
        InspectionMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            name=LocalizedText({"enGB": name}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _make_task(
    db,
    creator_id: int,
    *,
    method_id: int,
    lot_number: str,
    project_number: str,
    part_number: str,
    article_name: str,
    status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
    quantity: float = 10.0,
    planned_start: datetime | None = None,
    actual_end: datetime | None = None,
    operator_id: int | None = None,
) -> ProductionOrder:
    """One QA task: a lot with one position carrying an inspection step,
    and one production order on that position. With operator_id, a
    completion of one piece recorded by that operator is added, and the
    stored completed counts and statuses are the ones it derives."""
    n = next(_seq)
    completed = 1.0 if operator_id is not None else 0.0
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=project_number
        )
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=article_name,
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=part_number,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=quantity,
            status=LotStatus.IN_PROGRESS if completed else LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=(
                LotPositionStatus.PARTIALLY_COMPLETED
                if completed
                else LotPositionStatus.ORDERED_OR_QUEUED
            ),
            quantity=quantity,
            quantity_completed=completed,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    await lot_repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=None,
            estimated_setup_minutes=None,
            estimated_minutes_per_piece=None,
            sequence=1,
            creator_id=creator_id,
            fabrication_method_id=None,
            lot_id=lot.id,
            position_id=position.id,
            source_process_id=None,
            role=StepRole.INSPECTION,
            inspection_method_id=method_id,
        )
    )
    order_repo = SqlAlchemyProductionOrderRepository(db)
    order = await order_repo.save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-QA-{n}",
            status=status,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=n,
            quantity=quantity,
            quantity_completed=completed,
            estimated_duration_minutes=30,
            note=None,
            planned_start=planned_start,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=actual_end,
            creator_id=creator_id,
            machine_id=None,
            lot_position_id=position.id,
        )
    )
    await db.commit()
    if operator_id is not None:
        await order_repo.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=order.id,
                quantity=completed,
                quantity_accepted=completed,
                quantity_rejected=0.0,
                completion_date=date.today(),
                note=None,
                operator_id=operator_id,
                recorded_by_id=creator_id,
                created=datetime.now(UTC),
            )
        )
        await db.commit()
    return order


async def _pair(db, create_user, **overrides_b):
    """Two tasks that differ only where the test says. Returns (a, b, user,
    method_a). Task a is always the "default" one."""
    user = await create_user()
    method_a = await _make_inspection_method(db, user.id, "Visual")
    method_b = await _make_inspection_method(db, user.id, "CMM")
    base = {
        "method_id": method_a.id,
        "lot_number": "LN-26-00001",
        "project_number": "P26001",
        "part_number": "TN-26-00001",
        "article_name": "Shaft",
    }
    a = await _make_task(db, user.id, **base)
    # Lot, project and part number are unique keys, so task b gets its own
    # unless the test overrides them.
    b_kwargs = {
        **base,
        "method_id": method_b.id,
        "lot_number": "LN-26-00002",
        "project_number": "P26002",
        "part_number": "TN-26-00002",
        **overrides_b,
    }
    b = await _make_task(db, user.id, **b_kwargs)
    return a, b, user, method_a


async def _ids(db, **filters) -> set[int]:
    _, orders = await SqlAlchemyProductionOrderRepository(db).get_multi(
        ProductionOrderFilterDto(step_role=StepRole.INSPECTION.value, limit=200, **filters)
    )
    return {o.id for o in orders}


class TestQaTextFilters:
    async def test_lot_number(self, db, create_user):
        a, b, _, _ = await _pair(db, create_user, lot_number="LN-26-99999")
        assert await _ids(db, lot_number="ln-26-0000") == {a.id}
        assert await _ids(db, lot_number="99999") == {b.id}
        assert await _ids(db, lot_number="nothing") == set()

    async def test_lot_number_escapes_like_wildcards(self, db, create_user):
        await _pair(db, create_user)
        assert await _ids(db, lot_number="%") == set()

    async def test_project_number(self, db, create_user):
        a, b, _, _ = await _pair(db, create_user, project_number="P26777")
        assert await _ids(db, project_number="p26001") == {a.id}
        assert await _ids(db, project_number="777") == {b.id}

    async def test_item_text_matches_part_number_or_article_name(self, db, create_user):
        a, b, _, _ = await _pair(db, create_user, part_number="TN-26-00077", article_name="Flange")
        assert await _ids(db, item_text="-00001") == {a.id}
        assert await _ids(db, item_text="flan") == {b.id}
        assert await _ids(db, item_text="Bracket") == set()


class TestQaSelectFilters:
    async def test_inspection_method_any_of(self, db, create_user):
        a, b, _, method_a = await _pair(db, create_user)
        assert await _ids(db, step_inspection_method_ids=[method_a.id]) == {a.id}
        assert await _ids(db, step_inspection_method_ids=[method_a.id, method_a.id + 1]) == {
            a.id,
            b.id,
        }
        assert await _ids(db, step_inspection_method_ids=[999_999]) == set()

    async def test_finished_by_matches_completion_operator(self, db, create_user):
        user = await create_user()
        other = await create_user(username="qa-operator", email="qa-operator@example.com")
        method = await _make_inspection_method(db, user.id, "Visual")

        async def task(key: str, operator_id: int | None) -> ProductionOrder:
            return await _make_task(
                db,
                user.id,
                method_id=method.id,
                lot_number=f"LN-{key}",
                project_number=f"P-{key}",
                part_number=f"TN-{key}",
                article_name="Shaft",
                operator_id=operator_id,
            )

        a = await task("A", user.id)
        b = await task("B", other.id)
        await task("C", None)
        assert await _ids(db, finished_by_ids=[user.id]) == {a.id}
        assert await _ids(db, finished_by_ids=[user.id, other.id]) == {a.id, b.id}


class TestQaRangeFilters:
    async def test_quantity_bounds_are_inclusive(self, db, create_user):
        a, b, _, _ = await _pair(db, create_user, quantity=25.0)
        assert await _ids(db, quantity_min=10.0, quantity_max=10.0) == {a.id}
        assert await _ids(db, quantity_min=11.0) == {b.id}
        assert await _ids(db, quantity_max=24.0) == {a.id}

    async def test_planned_start_day_range_is_inclusive(self, db, create_user):
        # 23:30 on 20 September in Vienna, the tenant's timezone (CEST).
        a, b, _, _ = await _pair(
            db, create_user, planned_start=datetime(2026, 9, 20, 21, 30, tzinfo=UTC)
        )
        # Task a has no planned start and never matches a date bound.
        assert await _ids(
            db, planned_start_from=date(2026, 9, 20), planned_start_to=date(2026, 9, 20)
        ) == {b.id}
        assert await _ids(db, planned_start_to=date(2026, 9, 19)) == set()
        assert a.id not in await _ids(db, planned_start_from=date(2000, 1, 1))

    async def test_finished_day_range_is_inclusive(self, db, create_user, allow_lifecycle_drift):
        # Completed without completion rows, which the filter does not read.
        _, b, _, _ = await _pair(
            db,
            create_user,
            status=ProductionOrderStatus.COMPLETED,
            # 23:30 on 21 September in Vienna, the tenant's timezone (CEST).
            actual_end=datetime(2026, 9, 21, 21, 30, tzinfo=UTC),
        )
        assert await _ids(
            db, actual_end_from=date(2026, 9, 21), actual_end_to=date(2026, 9, 21)
        ) == {b.id}
        assert await _ids(db, actual_end_from=date(2026, 9, 22)) == set()


class TestQaFilterApi:
    """End to end through GET /production-qa. include_future is on so the
    readiness rule does not hide the unscheduled fixtures."""

    async def test_list_params_bind_from_repeated_keys(self, db, create_user, auth_client):
        a, _b, _, method_a = await _pair(db, create_user)
        client = await auth_client(username="qa-reader", email="qa-reader@example.com")
        response = await client.get(
            URL,
            params=[
                ("include_future", "true"),
                ("inspection_method_id", str(method_a.id)),
                ("inspection_method_id", "999999"),
            ],
        )
        assert response.status_code == 200, response.text
        assert {t["id"] for t in response.json()["items"]} == {a.id}
        assert response.json()["total"] == 1

    async def test_text_filters_reach_the_query(self, db, create_user, auth_client):
        _a, b, _, _ = await _pair(db, create_user, project_number="P26777")
        client = await auth_client(username="qa-reader", email="qa-reader@example.com")
        response = await client.get(URL, params={"include_future": "true", "project_number": "777"})
        assert response.status_code == 200, response.text
        assert [t["id"] for t in response.json()["items"]] == [b.id]

    async def test_status_pick_replaces_the_completed_toggle(
        self, db, create_user, auth_client, allow_lifecycle_drift
    ):
        # Completed without completion rows, which the filter does not read.
        a, b, _, _ = await _pair(db, create_user, status=ProductionOrderStatus.COMPLETED)
        client = await auth_client(username="qa-reader", email="qa-reader@example.com")
        default = await client.get(URL, params={"include_future": "true"})
        assert {t["id"] for t in default.json()["items"]} == {a.id}
        picked = await client.get(URL, params=[("include_future", "true"), ("status", "completed")])
        assert picked.status_code == 200, picked.text
        assert {t["id"] for t in picked.json()["items"]} == {b.id}

    async def test_quantity_min_above_max_is_rejected(self, auth_client):
        response = await (await auth_client()).get(
            URL, params={"quantity_min": 5, "quantity_max": 1}
        )
        assert response.status_code == 422
