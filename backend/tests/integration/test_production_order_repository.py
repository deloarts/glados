"""
DB-backed coverage for SqlAlchemyProductionOrderRepository,
unlike the rest of tests/integration/, this drives the repository directly
against the throwaway SQLite database rather than through HTTP, since
what's under test (the `lot_id` filter in get_multi, and assessment
enrichment) is repository/SQL behavior, not routing or the use-case layer.
Reuses tests/integration/conftest.py's `db` session and schema fixtures.

`GET /production-orders?lot_id=N` must return only that lot's orders, not
every production order in the system, and each ProductionOrder embeds its
manufacturing assessment directly, so the frontend needs no follow-up
fetch per order (N+1).
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import update

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.manufacturing_assessment_repository import (
    SqlAlchemyManufacturingAssessmentRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._lot_facts import give_lot_facts


async def _make_project(db, creator_id: int, number: str) -> Project:
    return await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=number)
    )


async def _make_made_item(db, creator_id: int, article_name: str) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
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
            part_number=None,
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
    return seeded


async def _make_lot_with_position(
    db, creator_id: int, made_item_id: int, project_id: int, lot_number: str
) -> tuple[ProductionLot, int]:
    """Returns the lot and its single position's id, every test here
    needs a lot_position_id to hang production orders off of."""
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=10.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item_id,
            project_id=project_id,
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
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    return lot, position.id


_order_number_seq = itertools.count(1)
# A partial unique index on (queue_sequence) per scope, live orders only.
# Every fixture below is QUEUED, i.e. live, so two orders built by this
# helper with the same machine_id (None included, since the unassigned
# scope is a scope too) and a hardcoded queue_sequence would collide at
# flush. One counter, module-global like _order_number_seq, keeps every
# order this file builds distinct regardless of scope, so no call site
# can miss it.
_queue_sequence_seq = itertools.count(1)


async def _make_order(
    db, creator_id: int, lot_position_id: int, *, machine_id: int | None = None
) -> ProductionOrder:
    return await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-TEST-{next(_order_number_seq)}",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=next(_queue_sequence_seq),
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine_id,
            lot_position_id=lot_position_id,
        )
    )


async def _make_machine(db, creator_id: int, internal_name: str) -> ProductionMachine:
    saved = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=internal_name,
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _make_completion(db, creator_id: int, order_id: int) -> ProductionOrderCompletion:
    """One accepted piece on the order, with the completed count the
    reconciler derives from it."""
    await db.execute(
        update(ProductionOrderOrmModel)
        .where(ProductionOrderOrmModel.id == order_id)
        .values(quantity_completed=ProductionOrderOrmModel.quantity_completed + 1.0)
    )
    return await SqlAlchemyProductionOrderRepository(db).save_completion(
        ProductionOrderCompletion(
            id=0,
            production_order_id=order_id,
            quantity=1.0,
            quantity_accepted=1.0,
            quantity_rejected=0.0,
            completion_date=date.today(),
            note=None,
            operator_id=creator_id,
            recorded_by_id=creator_id,
            created=datetime.now(UTC),
        )
    )


async def _seed_order_fanout(db, create_user, *, lot_count: int = 3) -> int:
    """Creates `lot_count` lots x 2 positions x 2 orders (12 orders for the
    default lot_count=3) on one machine, with >=3 distinct made
    items/projects, >=2 distinct creators, and >=1 completion per order,
    enough fan-out that a per-row N+1 and a batched read are
    distinguishable by round-trip count alone, regardless of row
    count. Returns the machine id.
    """
    creators = [
        await create_user(username=f"fanout-creator-{i}", email=f"fanout-creator-{i}@example.com")
        for i in range(2)
    ]
    machine = await _make_machine(db, creators[0].id, "FANOUT-MACHINE")
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot_ids: list[int] = []

    for lot_i in range(lot_count):
        creator = creators[lot_i % 2]
        project = await _make_project(db, creator.id, f"P-FANOUT-{lot_i}")
        made_item = await _make_made_item(db, creator.id, f"Fanout item {lot_i}")
        lot = await lot_repo.save(
            ProductionLot(
                id=0,
                created=datetime.now(UTC),
                changed=None,
                changes=[],
                lot_number=f"LN-FANOUT-{lot_i}",
                quantity=10.0,
                status=LotStatus.PLANNED,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=creator.id,
                made_item_id=made_item.id,
                project_id=project.id,
                input_demand_id=None,
            )
        )
        for pos_i in range(2):
            position = await lot_repo.save_position(
                LotPosition(
                    id=0,
                    created=datetime.now(UTC),
                    changed=None,
                    changes=[],
                    sequence=pos_i + 1,
                    kind=LotPositionKind.INTERNAL,
                    status=LotPositionStatus.ORDERED_OR_QUEUED,
                    quantity=5.0,
                    quantity_completed=0.0,
                    note=None,
                    creator_id=creator.id,
                    lot_id=lot.id,
                )
            )
            for order_i in range(2):
                order = await _make_order(
                    db,
                    creators[order_i % 2].id,
                    position.id,
                    machine_id=machine.id,
                )
                await _make_completion(db, creators[order_i % 2].id, order.id)
        lot_ids.append(lot.id)

    # The lots store what their completion rows derive, as after a
    # completion through the use case.
    await give_lot_facts(db, *lot_ids, exact=False)
    await db.commit()
    return machine.id


class TestGetMultiLotIdFilter:
    async def test_filters_to_only_the_requested_lot(self, db, create_user):
        user = await create_user()
        project = await _make_project(db, user.id, "P-LOTFILTER-1")
        made_item = await _make_made_item(db, user.id, "Filter target")

        lot_a, position_a = await _make_lot_with_position(
            db, user.id, made_item.id, project.id, "LN-FILTER-A"
        )
        _lot_b, position_b = await _make_lot_with_position(
            db, user.id, made_item.id, project.id, "LN-FILTER-B"
        )

        order_a = await _make_order(db, user.id, position_a)
        await _make_order(db, user.id, position_a)
        await _make_order(db, user.id, position_b)

        repo = SqlAlchemyProductionOrderRepository(db)
        total, orders = await repo.get_multi(ProductionOrderFilterDto(lot_id=lot_a.id, limit=200))

        assert total == 2
        assert len(orders) == 2
        assert {o.lot_id for o in orders} == {lot_a.id}
        assert order_a.id in {o.id for o in orders}

    async def test_unfiltered_call_still_returns_every_order(self, db, create_user):
        """Confirms the join is conditional, omitting lot_id must not
        narrow results to orders that happen to have a lot_position."""
        user = await create_user()
        project = await _make_project(db, user.id, "P-LOTFILTER-2")
        made_item = await _make_made_item(db, user.id, "Unfiltered target")
        _lot, position_id = await _make_lot_with_position(
            db, user.id, made_item.id, project.id, "LN-FILTER-C"
        )
        await _make_order(db, user.id, position_id)
        await _make_order(db, user.id, position_id)

        repo = SqlAlchemyProductionOrderRepository(db)
        total, orders = await repo.get_multi(ProductionOrderFilterDto(limit=200))

        assert total >= 2
        assert len(orders) >= 2


class TestGetMultiChangedFromFilter:
    async def test_keeps_orders_changed_or_created_since_the_instant(self, db, create_user):
        """An order counts by its last change, or by its creation when it was
        never changed, so a finished order an operator touched today stays on
        the board while one finished weeks ago drops off."""
        user = await create_user()
        project = await _make_project(db, user.id, "P-CHANGEDFROM-1")
        made_item = await _make_made_item(db, user.id, "Changed from target")
        _lot, position_id = await _make_lot_with_position(
            db, user.id, made_item.id, project.id, "LN-CHANGEDFROM-A"
        )
        stale = await _make_order(db, user.id, position_id)
        touched = await _make_order(db, user.id, position_id)
        fresh = await _make_order(db, user.id, position_id)
        long_ago = datetime(2026, 1, 1, tzinfo=UTC)
        cutoff = datetime(2026, 6, 1, tzinfo=UTC)
        orm = ProductionOrderOrmModel
        await db.execute(
            update(orm).where(orm.id.in_([stale.id, touched.id])).values(created=long_ago)
        )
        await db.execute(
            update(orm).where(orm.id == touched.id).values(changed=datetime(2026, 7, 1, tzinfo=UTC))
        )
        await db.execute(
            update(orm).where(orm.id == fresh.id).values(created=datetime(2026, 7, 2, tzinfo=UTC))
        )
        await db.commit()

        repo = SqlAlchemyProductionOrderRepository(db)
        _total, orders = await repo.get_multi(
            ProductionOrderFilterDto(lot_position_id=position_id, changed_from=cutoff, limit=200)
        )

        assert {o.id for o in orders} == {touched.id, fresh.id}


class TestAssessmentEnrichment:
    async def test_embeds_assessment_when_present_and_none_otherwise(self, db, create_user):
        user = await create_user()
        project = await _make_project(db, user.id, "P-ASSESS-1")
        made_item = await _make_made_item(db, user.id, "Assessment target")
        lot, position_id = await _make_lot_with_position(
            db, user.id, made_item.id, project.id, "LN-ASSESS-A"
        )

        assessed_order = await _make_order(db, user.id, position_id)
        unassessed_order = await _make_order(db, user.id, position_id)

        await SqlAlchemyManufacturingAssessmentRepository(db).save(
            ManufacturingAssessment(
                id=0,
                production_order_id=assessed_order.id,
                operator_id=user.id,
                actual_minutes_per_piece=5,
                actual_setup_minutes=10,
                complexity=ComplexityClass.NORMAL,
                note=None,
                created=datetime.now(UTC),
            )
        )

        repo = SqlAlchemyProductionOrderRepository(db)
        total, orders = await repo.get_multi(ProductionOrderFilterDto(lot_id=lot.id, limit=200))
        by_id = {o.id: o for o in orders}

        assert total == 2
        assert by_id[assessed_order.id].assessment is not None
        assert by_id[assessed_order.id].assessment.actual_minutes_per_piece == 5
        assert by_id[unassessed_order.id].assessment is None

        single = await repo.get_by_id(assessed_order.id)
        assert single is not None
        assert single.assessment is not None
        assert single.assessment.actual_minutes_per_piece == 5


class TestQueryCountRegression:
    """Pins the query count of `order_orm_to_entity`'s fan-out (11 lazily-loaded
    relationship accesses, plus a hidden second hop through
    `UserOrmModel.members` for every distinct creator/planned_by/
    completion-operator/completion-recorded_by) across the two read paths
    that pay for it on every call: `get_by_machine_id` (queue board) and
    `get_multi` (orders list).

    This harness pins the *actual* SQLite round-trip count for a fixture
    with known fan-out (3 lots, 2 positions each, 2 orders per position =
    12 orders, 2 creators, 3 made items/projects), which is
    dialect-independent for
    round-trip *count* even though SQLite's identity-map reuse across
    orders sharing a lot/creator noticeably reduces the total versus a
    naive "11 queries x 12 orders" estimate.

    Plain lazy loading through the mapper's bare relationships, with no
    loader options, costs get_by_machine_id 36 statements and get_multi 37
    (one extra for `total = q.count()`) for the 12-order fixture below.
    With per-query `selectinload` via `_order_loaders()` they cost 16 and
    17, batched down to a small constant number of IN-queries per
    relationship rather than one lazy load per row. That count is
    independent of row count (see the parametrized test below), which is
    the property that matters: it does not grow toward O(rows) as the
    table grows.
    """

    async def test_get_by_machine_id_query_count_is_bounded(self, db, create_user, query_counter):
        machine_id = await _seed_order_fanout(db, create_user)
        repo = SqlAlchemyProductionOrderRepository(db)

        with query_counter() as statements:
            orders = await repo.get_by_machine_id(machine_id)

        assert len(orders) == 12
        assert len(statements) == 17, "\n".join(statements)

    async def test_get_multi_query_count_is_bounded(self, db, create_user, query_counter):
        await _seed_order_fanout(db, create_user)
        repo = SqlAlchemyProductionOrderRepository(db)

        with query_counter() as statements:
            total, orders = await repo.get_multi(ProductionOrderFilterDto(limit=200))

        assert total == 12
        assert len(orders) == 12
        assert len(statements) == 18, "\n".join(statements)

    @pytest.mark.parametrize("lot_count", [1, 3])
    async def test_get_by_machine_id_query_count_is_independent_of_row_count(
        self, db, create_user, query_counter, lot_count
    ):
        """The eager-loaded fan-out is a fixed cost per call, not per row:
        4 orders (lot_count=1) and 12 orders (lot_count=3) must cost the
        same number of round trips."""
        machine_id = await _seed_order_fanout(db, create_user, lot_count=lot_count)
        repo = SqlAlchemyProductionOrderRepository(db)

        with query_counter() as statements:
            orders = await repo.get_by_machine_id(machine_id)

        assert len(orders) == lot_count * 4
        assert len(statements) == 17, "\n".join(statements)

    async def test_eager_loaded_read_matches_lazy_read(self, db, create_user):
        """Reading via the new eager-loaded query path must produce
        field-for-field identical entities to reading fresh from the
        database after the session's identity map is cleared: proof the
        loader options change query shape only, never the data."""
        machine_id = await _seed_order_fanout(db, create_user)
        repo = SqlAlchemyProductionOrderRepository(db)

        first_read = await repo.get_by_machine_id(machine_id)
        db.expunge_all()
        second_read = await repo.get_by_machine_id(machine_id)

        assert len(first_read) == len(second_read) == 12
        by_id_first = {o.id: o for o in first_read}
        by_id_second = {o.id: o for o in second_read}
        assert by_id_first.keys() == by_id_second.keys()
        for order_id, order_a in by_id_first.items():
            order_b = by_id_second[order_id]
            assert order_a == order_b, order_id
