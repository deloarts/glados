"""
The order list gains `source_item_id` and `made_item_id` filters that mirror
the existing `bought_item_id` filter end to end (OrderFilterDto ->
OrderFilterParams -> SqlAlchemyOrderRepository.get_multi). `made_item_id` has
no column of its
own on order_item_table: a MADE line's identity is only reachable through
lot_position -> production_lot, same chain test_order_item_naming.py's
TestOrderSearch already exercises for full-text search, so this file
imports that module's builders (`_order`, `_order_item`, `_made_item_line`)
rather than re-deriving the same fixture shape.
"""

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from tests.integration.test_order_item_naming import NOW
from tests.integration.test_order_item_naming import TODAY
from tests.integration.test_order_item_naming import _made_item_line
from tests.integration.test_order_item_naming import _order
from tests.integration.test_order_item_naming import _order_item


def _source_item(db, item_id: int, dimension: str) -> None:
    db.add(
        SourceItemTypeOrmModel(
            id=item_id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            name={"enGB": f"Type-{item_id}"},
            label_color="#000000",
            label_font_color="#ffffff",
            description={},
            creator_id=1,
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
            material="1.0037",
            type_id=item_id,
            creator_id=1,
        )
    )


def _bought_item(db, item_id: int, article_name: str) -> None:
    db.add(
        BoughtItemOrmModel(
            id=item_id,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            order_code_1=f"OC-{item_id}",
            status="open",
            article_name=article_name,
            part_number=f"PN-{item_id}",
            data_source="WEB",
            creator_id=1,
            manufacturer_id=1,
        )
    )


async def _made_item_line_2(db):
    """Same chain as test_order_item_naming's `_made_item_line`, a distinct
    id=2 chain throughout. The made_item_id filter's negative case needs a
    second MADE line whose lot belongs to a *different* made item."""
    db.add(
        MadeItemOrmModel(
            id=2,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            revision="A",
            article_name="Flange, machined",
            status="ACTIVE",
            data_source="WEB",
            creator_id=1,
            part_number="PN-FLANGE",
        )
    )
    db.add(
        ProductionLotOrmModel(
            id=2,
            created=TODAY,
            changes=[],
            lot_number="LOT-2026-0002",
            made_item_id=2,
            quantity=5.0,
            status="draft",
            priority="normal",
            creator_id=1,
            project_id=1,
        )
    )
    db.add(
        LotPositionOrmModel(
            id=2,
            created=TODAY,
            changes=[],
            lot_id=2,
            sequence=1,
            quantity=5.0,
            quantity_completed=0.0,
            kind="external",
            status="pending",
            creator_id=1,
        )
    )
    _order(db, order_id=2)
    return await _order_item(
        db, id=2, order_id=2, line_type="MADE", lot_position_id=2, virtual_name=None
    )


class TestSourceItemIdFilter:
    async def test_returns_only_the_order_carrying_that_source_item(self, db):
        _source_item(db, item_id=1, dimension="40x40x4")
        _source_item(db, item_id=2, dimension="20x20x2")
        _order(db, order_id=1)
        await _order_item(db, id=1, order_id=1, line_type="SOURCE", source_item_id=1)
        _order(db, order_id=2)
        await _order_item(db, id=2, order_id=2, line_type="SOURCE", source_item_id=2)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(source_item_id=1)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_does_not_match_a_different_source_item(self, db):
        _source_item(db, item_id=1, dimension="40x40x4")
        _source_item(db, item_id=2, dimension="20x20x2")
        _order(db, order_id=1)
        await _order_item(db, id=1, order_id=1, line_type="SOURCE", source_item_id=1)
        _order(db, order_id=2)
        await _order_item(db, id=2, order_id=2, line_type="SOURCE", source_item_id=2)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(source_item_id=2)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-2"]


class TestMadeItemIdFilter:
    async def test_returns_only_the_order_whose_lot_is_for_that_made_item(self, db):
        await _made_item_line(db)  # made_item_id=1, order O-1
        await _made_item_line_2(db)  # made_item_id=2, order O-2

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(made_item_id=1)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_does_not_match_a_different_made_item(self, db):
        await _made_item_line(db)  # made_item_id=1, order O-1
        await _made_item_line_2(db)  # made_item_id=2, order O-2

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(made_item_id=2)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-2"]


class TestBoughtItemIdFilterStillWorks:
    """Regression guard: adding source_item_id/made_item_id alongside it
    must not disturb the pre-existing bought_item_id branch."""

    async def test_returns_only_the_order_carrying_that_bought_item(self, db):
        _bought_item(db, item_id=1, article_name="Hex bolt M8")
        _bought_item(db, item_id=2, article_name="Hex nut M8")
        _order(db, order_id=1)
        await _order_item(db, id=1, order_id=1, bought_item_id=1)
        _order(db, order_id=2)
        await _order_item(db, id=2, order_id=2, bought_item_id=2)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(bought_item_id=1)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_does_not_match_a_different_bought_item(self, db):
        _bought_item(db, item_id=1, article_name="Hex bolt M8")
        _bought_item(db, item_id=2, article_name="Hex nut M8")
        _order(db, order_id=1)
        await _order_item(db, id=1, order_id=1, bought_item_id=1)
        _order(db, order_id=2)
        await _order_item(db, id=2, order_id=2, bought_item_id=2)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(bought_item_id=2)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-2"]


def _order_with_text(db, order_id: int, note: str | None = None, storage_place: str | None = None):
    order = _order(db, order_id=order_id)
    order.note = note
    order.storage_place = storage_place
    return order


async def _order_numbers(filters: OrderFilterDto, db) -> list[str]:
    _total, orders = await SqlAlchemyOrderRepository(db).get_multi(filters)
    return sorted(o.order_number for o in orders)


class TestNoteFilter:
    """`note` is a case-insensitive substring match on the order's own note
    column, with LIKE wildcards in the term escaped so they match literally."""

    async def test_matches_a_substring_case_insensitively(self, db):
        _order_with_text(db, order_id=1, note="Urgent, call before delivery")
        _order_with_text(db, order_id=2, note="Standard order")
        await db.commit()

        assert await _order_numbers(OrderFilterDto(note="URGENT"), db) == ["O-1"]

    async def test_does_not_match_an_order_without_that_note(self, db):
        _order_with_text(db, order_id=1, note="Urgent, call before delivery")
        _order_with_text(db, order_id=2, note=None)
        await db.commit()

        assert await _order_numbers(OrderFilterDto(note="standard"), db) == []

    async def test_escapes_like_wildcards_in_the_term(self, db):
        _order_with_text(db, order_id=1, note="Discount 10% agreed")
        _order_with_text(db, order_id=2, note="Discount 10 EUR agreed")
        _order_with_text(db, order_id=3, note="ref_42")
        _order_with_text(db, order_id=4, note="ref-42")
        await db.commit()

        assert await _order_numbers(OrderFilterDto(note="10%"), db) == ["O-1"]
        assert await _order_numbers(OrderFilterDto(note="ref_"), db) == ["O-3"]


class TestStoragePlaceFilter:
    """`storage_place` mirrors `note`: substring, case-insensitive, escaped."""

    async def test_matches_a_substring_case_insensitively(self, db):
        _order_with_text(db, order_id=1, storage_place="Shelf A-12")
        _order_with_text(db, order_id=2, storage_place="Rack B-3")
        await db.commit()

        assert await _order_numbers(OrderFilterDto(storage_place="shelf a"), db) == ["O-1"]

    async def test_does_not_match_an_order_stored_elsewhere(self, db):
        _order_with_text(db, order_id=1, storage_place="Shelf A-12")
        _order_with_text(db, order_id=2, storage_place=None)
        await db.commit()

        assert await _order_numbers(OrderFilterDto(storage_place="Rack"), db) == []

    async def test_escapes_like_wildcards_in_the_term(self, db):
        _order_with_text(db, order_id=1, storage_place="Bin 5%")
        _order_with_text(db, order_id=2, storage_place="Bin 5")
        _order_with_text(db, order_id=3, storage_place="Bay_7")
        _order_with_text(db, order_id=4, storage_place="Bay-7")
        await db.commit()

        assert await _order_numbers(OrderFilterDto(storage_place="5%"), db) == ["O-1"]
        assert await _order_numbers(OrderFilterDto(storage_place="Bay_"), db) == ["O-3"]

    async def test_note_and_storage_place_are_anded(self, db):
        _order_with_text(db, order_id=1, note="Urgent", storage_place="Shelf A")
        _order_with_text(db, order_id=2, note="Urgent", storage_place="Rack B")
        _order_with_text(db, order_id=3, note="Standard", storage_place="Shelf A")
        await db.commit()

        assert await _order_numbers(OrderFilterDto(note="urgent", storage_place="shelf"), db) == [
            "O-1"
        ]


class TestGetByIds:
    """SqlAlchemyOrderRepository.get_by_ids, the batch counterpart to
    get_by_id used by the allocation read paths to avoid one query per
    order. No dedicated order-repository test file exists yet, so this
    lives alongside the other SqlAlchemyOrderRepository coverage here."""

    async def test_empty_list_returns_empty_list(self, db):
        _order(db, order_id=1)
        await db.commit()

        assert await SqlAlchemyOrderRepository(db).get_by_ids([]) == []

    async def test_missing_id_in_a_subset_is_simply_omitted(self, db):
        _order(db, order_id=1)
        _order(db, order_id=2)
        await db.commit()

        orders = await SqlAlchemyOrderRepository(db).get_by_ids([1, 999, 2])

        assert {o.order_number for o in orders} == {"O-1", "O-2"}
        assert len(orders) == 2

    async def test_result_is_order_independent_and_matches_get_by_id(self, db):
        _order(db, order_id=1)
        _order(db, order_id=2)
        await db.commit()
        repo = SqlAlchemyOrderRepository(db)

        by_ids = {o.id: o for o in await repo.get_by_ids([2, 1])}

        assert by_ids[1] == await repo.get_by_id(1)
        assert by_ids[2] == await repo.get_by_id(2)
