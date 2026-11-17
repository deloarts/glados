"""
DB-backed coverage for the column filters the three demand tables send
beyond status and bucket: the order and lot lookups matched through the
allocation tables, the made-item routing method filter, and the source
demand project, item, and desired-delivery filters.

Rows are inserted through the ORM directly where the use cases would drag
in unrelated aggregates. The test database is SQLite without foreign key
enforcement, so referenced orders, lots, and method rows need not exist
for a predicate that only compares ids.

Multi-value parameters are any-of within the field and AND across fields,
which each list-typed test pins with one matching, one non-matching and
one combined case. The tables' default order, newest first, and the sort
by project number are pinned at the end.
"""

from datetime import date
from itertools import count
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model import (
    MadeItemProcessOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from tests.integration._demand_facts import give_demand_facts
from tests.integration.test_demand_allocation_filters import _bought_demand
from tests.integration.test_demand_allocation_filters import _project
from tests.integration.test_order_item_naming import NOW
from tests.integration.test_order_item_naming import _order_item

# ── Arrangement helpers ───────────────────────────────────────────────

# A production lot holds at most one source demand, so demands that do not
# pin a lot themselves each take a fresh one. Tables are cleared per test.
_free_lot_ids = count(1000)


async def _bought_order_allocation(db: AsyncSession, demand_id: int, order_item_id: int) -> None:
    db.add(
        BoughtItemAllocationOrmModel(
            demand_item_id=demand_id, order_item_id=order_item_id, source="order", quantity=1.0
        )
    )
    await give_demand_facts(db, LifecycleAggregate.BOUGHT_DEMANDS, demand_id, expected="allocated")
    await db.commit()


async def _made_demand(
    db: AsyncSession, creator_id: int, project_id: int, *, made_item_id: int
) -> int:
    demand = await SqlAlchemyMadeItemDemandItemRepository(db).save(
        MadeItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=MadeItemDemandStatus.OPEN,
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
        )
    )
    return demand.id


async def _made_lot_allocation(db: AsyncSession, demand_id: int, lot_id: int) -> None:
    db.add(
        MadeItemAllocationOrmModel(
            demand_item_id=demand_id, lot_id=lot_id, source="lot", quantity=1.0
        )
    )
    await give_demand_facts(db, LifecycleAggregate.MADE_DEMANDS, demand_id, expected="allocated")
    await db.commit()


async def _process(
    db: AsyncSession,
    creator_id: int,
    made_item_id: int,
    *,
    fabrication_method_id: int | None = None,
    inspection_method_id: int | None = None,
) -> None:
    role = StepRole.INSPECTION if inspection_method_id is not None else StepRole.FABRICATION
    db.add(
        MadeItemProcessOrmModel(
            created=date.today(),
            made_item_id=made_item_id,
            fabrication_method_id=fabrication_method_id,
            inspection_method_id=inspection_method_id,
            role=role.value,
            position=1,
            group_index=0,
            creator_id=creator_id,
        )
    )
    await db.commit()


async def _source_item(
    db: AsyncSession,
    creator_id: int,
    item_id: int,
    *,
    dimension: str,
    material: str,
    type_name: str,
) -> None:
    db.add(
        SourceItemTypeOrmModel(
            id=item_id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            name={"enGB": type_name},
            label_color="#000000",
            label_font_color="#ffffff",
            description={},
            creator_id=creator_id,
        )
    )
    db.add(
        SourceItemOrmModel(
            id=item_id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            dimension=dimension,
            material=material,
            type_id=item_id,
            creator_id=creator_id,
        )
    )
    await db.commit()


async def _source_demand(
    db: AsyncSession,
    creator_id: int,
    project_id: int,
    *,
    lot_id: int | None = None,
    source_item_id: int | None = None,
    desired_delivery_date: date | None = None,
) -> int:
    if lot_id is None:
        lot_id = next(_free_lot_ids)
    demand = await SqlAlchemySourceItemDemandRepository(db).save(
        SourceItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=SourceItemDemandStatus.OPEN,
            quantity=5.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=desired_delivery_date,
            creator_id=creator_id,
            bought_item_id=None,
            source_item_id=source_item_id,
            lot_id=lot_id,
            project_id=project_id,
        )
    )
    return demand.id


async def _source_order_allocation(db: AsyncSession, demand_id: int, order_item_id: int) -> None:
    db.add(
        SourceItemAllocationOrmModel(
            demand_item_id=demand_id, order_item_id=order_item_id, source="order", quantity=1.0
        )
    )
    await give_demand_facts(db, LifecycleAggregate.SOURCE_DEMANDS, demand_id, expected="allocated")
    await db.commit()


async def _bought_ids(db: AsyncSession, **filters: Any) -> tuple[int, list[int]]:
    total, demands = await SqlAlchemyBoughtItemDemandItemRepository(db).get_multi(
        DemandItemFilterDto(**filters)
    )
    return total, sorted(d.id for d in demands)


async def _made_ids(db: AsyncSession, **filters: Any) -> tuple[int, list[int]]:
    total, demands = await SqlAlchemyMadeItemDemandItemRepository(db).get_multi(
        MadeItemDemandFilterDto(**filters)
    )
    return total, sorted(d.id for d in demands)


async def _source_ids(db: AsyncSession, **filters: Any) -> tuple[int, list[int]]:
    total, demands = await SqlAlchemySourceItemDemandRepository(db).get_multi(
        SourceItemDemandFilterDto(**filters)
    )
    return total, sorted(d.id for d in demands)


# ── Bought-item demands ───────────────────────────────────────────────


class TestBoughtDemandOrderFilter:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        """Demand A allocated from order 1, demand B from order 2, demand C
        without any allocation."""
        project_id = await _project(db, creator_id, "P-BO-1")
        await _order_item(db, id=10, order_id=1, bought_item_id=1)
        await _order_item(db, id=20, order_id=2, bought_item_id=1)
        a = await _bought_demand(db, creator_id, project_id, quantity=5.0)
        b = await _bought_demand(db, creator_id, project_id, quantity=5.0)
        c = await _bought_demand(db, creator_id, project_id, quantity=5.0)
        await _bought_order_allocation(db, a, order_item_id=10)
        await _bought_order_allocation(db, b, order_item_id=20)
        return a, b, c

    async def test_matches_demands_allocated_from_the_order(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _bought_ids(db, order_id=[1]) == (1, [a])

    async def test_is_any_of_across_orders(self, db, create_user):
        a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _bought_ids(db, order_id=[1, 2]) == (2, [a, b])

    async def test_unknown_order_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _bought_ids(db, order_id=[99]) == (0, [])

    async def test_several_allocations_from_one_order_count_once(self, db, create_user):
        """EXISTS, not a join: two order items of the same order must not
        duplicate the demand row or its total."""
        user = await create_user()
        project_id = await _project(db, user.id, "P-BO-2")
        await _order_item(db, id=10, order_id=1, bought_item_id=1)
        await _order_item(db, id=11, order_id=1, bought_item_id=1)
        a = await _bought_demand(db, user.id, project_id, quantity=5.0)
        await _bought_order_allocation(db, a, order_item_id=10)
        await _bought_order_allocation(db, a, order_item_id=11)

        assert await _bought_ids(db, order_id=[1]) == (1, [a])


# ── Made-item demands ─────────────────────────────────────────────────


class TestMadeDemandLotFilter:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        project_id = await _project(db, creator_id, "P-ML-1")
        a = await _made_demand(db, creator_id, project_id, made_item_id=1)
        b = await _made_demand(db, creator_id, project_id, made_item_id=1)
        c = await _made_demand(db, creator_id, project_id, made_item_id=1)
        await _made_lot_allocation(db, a, lot_id=1)
        await _made_lot_allocation(db, b, lot_id=2)
        return a, b, c

    async def test_matches_demands_allocated_from_the_lot(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, lot_id=[1]) == (1, [a])

    async def test_is_any_of_across_lots(self, db, create_user):
        a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, lot_id=[1, 2]) == (2, [a, b])

    async def test_unknown_lot_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, lot_id=[99]) == (0, [])


class TestMadeDemandProcessMethodFilter:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        """Item 1 is fabricated with method 5, item 2 is inspected with
        method 8, item 3 has no routing at all. One demand per item."""
        project_id = await _project(db, creator_id, "P-MP-1")
        await _process(db, creator_id, made_item_id=1, fabrication_method_id=5)
        await _process(db, creator_id, made_item_id=2, inspection_method_id=8)
        a = await _made_demand(db, creator_id, project_id, made_item_id=1)
        b = await _made_demand(db, creator_id, project_id, made_item_id=2)
        c = await _made_demand(db, creator_id, project_id, made_item_id=3)
        return a, b, c

    async def test_fabrication_method_matches_the_items_routing(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, process_fabrication_method_id=[5]) == (1, [a])

    async def test_fabrication_method_not_in_routing_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, process_fabrication_method_id=[6]) == (0, [])

    async def test_inspection_method_matches_the_items_routing(self, db, create_user):
        _a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, process_inspection_method_id=[8]) == (1, [b])

    async def test_inspection_method_not_in_routing_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _made_ids(db, process_inspection_method_id=[9]) == (0, [])

    async def test_fabrication_list_is_any_of(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-MP-2")
        await _process(db, user.id, made_item_id=1, fabrication_method_id=5)
        await _process(db, user.id, made_item_id=2, fabrication_method_id=6)
        a = await _made_demand(db, user.id, project_id, made_item_id=1)
        b = await _made_demand(db, user.id, project_id, made_item_id=2)
        await _made_demand(db, user.id, project_id, made_item_id=3)

        assert await _made_ids(db, process_fabrication_method_id=[5, 6]) == (2, [a, b])

    async def test_both_lists_combine_as_any_of(self, db, create_user):
        """One EXISTS with the two lists OR'ed inside: a demand whose item
        only fabricates and one whose item only inspects both match."""
        a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _made_ids(
            db, process_fabrication_method_id=[5], process_inspection_method_id=[8]
        ) == (2, [a, b])

    async def test_several_matching_processes_count_once(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-MP-3")
        await _process(db, user.id, made_item_id=1, fabrication_method_id=5)
        await _process(db, user.id, made_item_id=1, fabrication_method_id=5)
        a = await _made_demand(db, user.id, project_id, made_item_id=1)

        assert await _made_ids(db, process_fabrication_method_id=[5]) == (1, [a])


# ── Source-item demands ───────────────────────────────────────────────


class TestSourceDemandLotFilter:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        project_id = await _project(db, creator_id, "P-SL-1")
        a = await _source_demand(db, creator_id, project_id, lot_id=1)
        b = await _source_demand(db, creator_id, project_id, lot_id=2)
        c = await _source_demand(db, creator_id, project_id, lot_id=3)
        return a, b, c

    async def test_single_lot_id_still_matches(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, lot_id=[1]) == (1, [a])

    async def test_is_any_of_across_lots(self, db, create_user):
        a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, lot_id=[1, 2]) == (2, [a, b])

    async def test_unknown_lot_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, lot_id=[99]) == (0, [])

    async def test_single_value_query_key_binds_as_one_element_list(
        self, db, create_user, auth_client
    ):
        """The scalar form `?lot_id=1` the lot detail view sends binds as a
        one-element list."""
        arranger = await create_user(username="arranger", email="arranger@example.com")
        a, _b, _c = await self._arrange(db, arranger.id)
        client = await auth_client()

        resp = await client.get("/api/v1/web/source-item-demands/", params={"lot_id": 1})

        assert resp.status_code == 200, resp.text
        assert [d["id"] for d in resp.json()["items"]] == [a]


class TestSourceDemandProjectNumberFilter:
    async def test_partial_case_insensitive_match(self, db, create_user):
        user = await create_user()
        alpha = await _project(db, user.id, "P-SRC-ALPHA")
        beta = await _project(db, user.id, "P-SRC-BETA")
        a = await _source_demand(db, user.id, alpha)
        await _source_demand(db, user.id, beta)

        assert await _source_ids(db, project_number="src-alpha") == (1, [a])

    async def test_unknown_project_number_matches_nothing(self, db, create_user):
        user = await create_user()
        project_id = await _project(db, user.id, "P-SRC-ALPHA")
        await _source_demand(db, user.id, project_id)

        assert await _source_ids(db, project_number="GAMMA") == (0, [])


class TestSourceDemandItemFilters:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        """Two source-item-backed demands sharing a dimension but differing
        in material and type, plus one demand without a source item."""
        project_id = await _project(db, creator_id, "P-SI-1")
        await _source_item(
            db, creator_id, 1, dimension="20x20", material="1.0037", type_name="Flat bar"
        )
        await _source_item(
            db, creator_id, 2, dimension="20x20", material="1.4301", type_name="Round bar"
        )
        a = await _source_demand(db, creator_id, project_id, source_item_id=1)
        b = await _source_demand(db, creator_id, project_id, source_item_id=2)
        c = await _source_demand(db, creator_id, project_id, source_item_id=None)
        return a, b, c

    async def test_dimension_matches_both_items_and_skips_itemless_demand(self, db, create_user):
        a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, item_dimension="20x") == (2, [a, b])

    async def test_dimension_not_present_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, item_dimension="30x30") == (0, [])

    async def test_material_matches_one_item(self, db, create_user):
        _a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, item_material="4301") == (1, [b])

    async def test_material_not_present_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, item_material="9.9999") == (0, [])

    async def test_type_matches_the_type_name(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, item_type="flat") == (1, [a])

    async def test_type_not_present_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, item_type="Sheet") == (0, [])

    async def test_three_inputs_are_anded(self, db, create_user):
        _a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(
            db, item_dimension="20x20", item_material="1.4301", item_type="round"
        ) == (1, [b])
        assert await _source_ids(
            db, item_dimension="20x20", item_material="1.4301", item_type="flat"
        ) == (0, [])


class TestSourceDemandSearch:
    """The list's search box: one term against project, lot, material,
    type and note, any of which may match."""

    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        return await TestSourceDemandItemFilters()._arrange(db, creator_id)

    async def test_matches_the_material(self, db, create_user):
        _a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, search="4301") == (1, [b])

    async def test_matches_the_type_name(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, search="flat") == (1, [a])

    async def test_matches_the_project_for_every_demand(self, db, create_user):
        a, b, c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, search="p-si-1") == (3, [a, b, c])

    async def test_an_unknown_term_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, search="zzz-nothing") == (0, [])


class TestSourceDemandOrderFilter:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int]:
        project_id = await _project(db, creator_id, "P-SO-1")
        await _order_item(db, id=10, order_id=1, line_type="SOURCE", source_item_id=1)
        await _order_item(db, id=20, order_id=2, line_type="SOURCE", source_item_id=1)
        a = await _source_demand(db, creator_id, project_id)
        b = await _source_demand(db, creator_id, project_id)
        c = await _source_demand(db, creator_id, project_id)
        await _source_order_allocation(db, a, order_item_id=10)
        await _source_order_allocation(db, b, order_item_id=20)
        return a, b, c

    async def test_matches_demands_allocated_from_the_order(self, db, create_user):
        a, _b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, order_id=[1]) == (1, [a])

    async def test_is_any_of_across_orders(self, db, create_user):
        a, b, _c = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, order_id=[1, 2]) == (2, [a, b])

    async def test_unknown_order_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, order_id=[99]) == (0, [])


class TestSourceDemandDesiredDeliveryFilter:
    async def _arrange(self, db: AsyncSession, creator_id: int) -> tuple[int, int, int, int]:
        project_id = await _project(db, creator_id, "P-SD-1")
        early = await _source_demand(
            db, creator_id, project_id, desired_delivery_date=date(2026, 9, 1)
        )
        mid = await _source_demand(
            db, creator_id, project_id, desired_delivery_date=date(2026, 9, 15)
        )
        late = await _source_demand(
            db, creator_id, project_id, desired_delivery_date=date(2026, 9, 30)
        )
        undated = await _source_demand(db, creator_id, project_id, desired_delivery_date=None)
        return early, mid, late, undated

    async def test_from_is_inclusive(self, db, create_user):
        _early, mid, late, _undated = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, desired_from=date(2026, 9, 15)) == (2, [mid, late])

    async def test_to_is_inclusive(self, db, create_user):
        early, mid, _late, _undated = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, desired_to=date(2026, 9, 15)) == (2, [early, mid])

    async def test_range_bounds_both_sides(self, db, create_user):
        _early, mid, _late, _undated = await self._arrange(db, (await create_user()).id)

        assert await _source_ids(
            db, desired_from=date(2026, 9, 2), desired_to=date(2026, 9, 29)
        ) == (
            1,
            [mid],
        )

    async def test_range_outside_all_dates_matches_nothing(self, db, create_user):
        await self._arrange(db, (await create_user()).id)

        assert await _source_ids(db, desired_from=date(2026, 10, 1)) == (0, [])


# ── Ordering ──────────────────────────────────────────────────────────


async def _ordered(repo: Any, dto: Any) -> list[int]:
    _total, demands = await repo.get_multi(dto)
    return [d.id for d in demands]


class TestDemandOrdering:
    """Every demand table lists the newest demand first unless a sort is
    chosen, and sorts by project number on request."""

    async def test_bought_demands(self, db, create_user):
        user = await create_user()
        later_project = await _project(db, user.id, "P-ORD-B")
        earlier_project = await _project(db, user.id, "P-ORD-A")
        first = await _bought_demand(db, user.id, later_project, quantity=1.0)
        second = await _bought_demand(db, user.id, earlier_project, quantity=1.0)
        repo = SqlAlchemyBoughtItemDemandItemRepository(db)

        assert await _ordered(repo, DemandItemFilterDto()) == [second, first]
        by_project = DemandItemFilterDto(order_by="project_number", order_dir="asc")
        assert await _ordered(repo, by_project) == [second, first]
        by_project_desc = DemandItemFilterDto(order_by="project_number", order_dir="desc")
        assert await _ordered(repo, by_project_desc) == [first, second]

    async def test_made_demands(self, db, create_user):
        user = await create_user()
        later_project = await _project(db, user.id, "P-ORD-B")
        earlier_project = await _project(db, user.id, "P-ORD-A")
        first = await _made_demand(db, user.id, later_project, made_item_id=1)
        second = await _made_demand(db, user.id, earlier_project, made_item_id=1)
        repo = SqlAlchemyMadeItemDemandItemRepository(db)

        assert await _ordered(repo, MadeItemDemandFilterDto()) == [second, first]
        by_project = MadeItemDemandFilterDto(order_by="project_number", order_dir="desc")
        assert await _ordered(repo, by_project) == [first, second]

    async def test_source_demands(self, db, create_user):
        user = await create_user()
        later_project = await _project(db, user.id, "P-ORD-B")
        earlier_project = await _project(db, user.id, "P-ORD-A")
        first = await _source_demand(db, user.id, earlier_project)
        second = await _source_demand(db, user.id, later_project)
        repo = SqlAlchemySourceItemDemandRepository(db)

        assert await _ordered(repo, SourceItemDemandFilterDto()) == [second, first]
        by_project = SourceItemDemandFilterDto(order_by="project_number", order_dir="asc")
        assert await _ordered(repo, by_project) == [first, second]
        # The project filter joins the project too; both together join it once.
        filtered = SourceItemDemandFilterDto(
            project_number="P-ORD", order_by="project_number", order_dir="desc"
        )
        assert await _ordered(repo, filtered) == [second, first]
