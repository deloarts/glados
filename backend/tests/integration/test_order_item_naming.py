"""
How an order line gets its display name, per line type.

The invariant under test is that a line's name is *resolved* from its own
catalogue row on every read rather than copied onto the line at creation.
That distinction is invisible until someone renames a catalogue entry:
with a copy, lines already sitting on an order keep the old name forever.
Only VIRTUAL lines, which have no catalogue row at all, store a name.

These run against a real session and the real repository mapper because
the resolution happens in the mapper's relationship traversal
(lot_position -> lot -> made_item), which a hand-built entity would not
exercise.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy import select

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
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_item_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository._mappers import (
    order_item_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from tests.integration._suppliers import seed_supplier

TODAY = date(2026, 8, 6)


async def _loaded(db, orm: OrderItemOrmModel) -> OrderItemOrmModel:
    """Re-reads a line with the relationships its mapper reads, the way the
    repository does; relationships are never loaded implicitly. The id is
    read from the identity key, which survives `expire_all()` without the
    implicit refresh an async session cannot do."""
    return (
        await db.scalars(
            select(OrderItemOrmModel)
            .where(OrderItemOrmModel.id == inspect(orm).identity[0])
            .options(*order_item_load_options())
            .execution_options(populate_existing=True)
        )
    ).one()


NOW = datetime(2026, 8, 6, tzinfo=UTC)


def _order(db, order_id: int = 1):
    order = OrderOrmModel(
        id=order_id,
        created=TODAY,
        changes=[],
        order_number=f"O-{order_id}",
        status="draft",
        creator_id=1,
        supplier_id=1,
    )
    db.add(order)
    return order


async def _order_item(db, **overrides) -> OrderItemOrmModel:
    defaults = dict(
        id=1,
        created=TODAY,
        changes=[],
        status="pending",
        position=1,
        quantity=1.0,
        quantity_delivered=0.0,
        unit="PCS",
        items_per_unit=1.0,
        creator_id=1,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type="BOUGHT",
    )
    item = OrderItemOrmModel(**{**defaults, **overrides})
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _made_item_line(db, article_name: str = "Bracket, welded") -> OrderItemOrmModel:
    """A MADE line and the whole chain it resolves its name through."""
    db.add(
        MadeItemOrmModel(
            id=1,
            created=NOW,
            changed=NOW,
            changes=[],
            archived=False,
            revision="A",
            article_name=article_name,
            status="ACTIVE",
            data_source="WEB",
            creator_id=1,
            part_number="PN-BRACKET",
        )
    )
    db.add(
        ProductionLotOrmModel(
            id=1,
            created=TODAY,
            changes=[],
            lot_number="LOT-2026-0001",
            made_item_id=1,
            quantity=5.0,
            status="draft",
            priority="normal",
            creator_id=1,
            project_id=1,
        )
    )
    db.add(
        LotPositionOrmModel(
            id=1,
            created=TODAY,
            changes=[],
            lot_id=1,
            sequence=1,
            quantity=5.0,
            quantity_completed=0.0,
            kind="external",
            status="pending",
            creator_id=1,
        )
    )
    _order(db)
    return await _order_item(db, line_type="MADE", lot_position_id=1, virtual_name=None)


class TestMadeLineNaming:
    async def test_name_comes_from_the_lots_made_item(self, db):
        entity = order_item_orm_to_entity(await _loaded(db, await _made_item_line(db)))

        assert entity.item_article_name == "Bracket, welded"
        assert entity.made_item_id == 1
        assert entity.item_part_number == "PN-BRACKET"
        assert entity.lot_number == "LOT-2026-0001"
        # No bought-catalogue link, and no stored copy of the name.
        assert entity.bought_item_id is None
        assert entity.virtual_name is None
        # A MadeItem has no order code of its own, and no specification
        # descriptor either (that's SOURCE-line-only).
        assert entity.item_order_code_1 == ""
        assert entity.item_order_code_2 is None
        assert entity.item_specification == ""

    async def test_renaming_the_made_item_renames_lines_already_ordered(self, db):
        orm = await _made_item_line(db)
        assert (
            order_item_orm_to_entity(await _loaded(db, orm)).item_article_name == "Bracket, welded"
        )

        made_item = await db.get(MadeItemOrmModel, 1)
        made_item.article_name = "Bracket, welded (rev B)"
        await db.commit()

        db.expire_all()
        reread = await _loaded(db, orm)
        assert order_item_orm_to_entity(reread).item_article_name == "Bracket, welded (rev B)"


class TestOtherLineTypesNaming:
    async def test_bought_line_resolves_from_its_bought_item(self, db):
        db.add(
            BoughtItemOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                order_code_1="OC-1",
                order_code_2="OC-2",
                status="open",
                article_name="Hex bolt M8",
                part_number="PN-BOLT",
                data_source="WEB",
                creator_id=1,
                manufacturer_id=1,
            )
        )
        _order(db)
        entity = order_item_orm_to_entity(
            await _loaded(db, await _order_item(db, bought_item_id=1))
        )

        assert entity.item_article_name == "Hex bolt M8"
        assert entity.item_order_code_1 == "OC-1"
        assert entity.item_order_code_2 == "OC-2"
        assert entity.item_part_number == "PN-BOLT"
        assert entity.virtual_name is None
        # BOUGHT lines never carry the SOURCE-only specification descriptor.
        assert entity.item_specification == ""

    async def test_source_line_resolves_from_its_source_item(self, db):
        db.add(
            SourceItemTypeOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                name={"enGB": "Round bar"},
                label_color="#000000",
                label_font_color="#ffffff",
                description={},
                creator_id=1,
            )
        )
        db.add(
            SourceItemOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                dimension="40x40x4",
                material="1.0037",
                type_id=1,
                order_code_1="SC-1",
                order_code_2="SC-2",
                creator_id=1,
            )
        )
        _order(db)
        entity = order_item_orm_to_entity(
            await _loaded(db, await _order_item(db, line_type="SOURCE", source_item_id=1))
        )

        assert entity.item_article_name == "40x40x4"
        assert entity.virtual_name is None
        # Real catalogue order codes, same as a BOUGHT line: that is the
        # point of the un-mixing.
        assert entity.item_order_code_1 == "SC-1"
        assert entity.item_order_code_2 == "SC-2"
        assert entity.item_specification == "1.0037 | Round bar"

    async def test_source_line_with_no_order_codes_still_has_a_specification(self, db):
        """The two concerns are genuinely separate: a SOURCE line's
        specification is derived from material/type regardless of whether
        the source item has supplier order codes at all."""
        db.add(
            SourceItemTypeOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                name={"enGB": "Round bar"},
                label_color="#000000",
                label_font_color="#ffffff",
                description={},
                creator_id=1,
            )
        )
        db.add(
            SourceItemOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                dimension="40x40x4",
                material="1.0037",
                type_id=1,
                creator_id=1,
            )
        )
        _order(db)
        entity = order_item_orm_to_entity(
            await _loaded(db, await _order_item(db, line_type="SOURCE", source_item_id=1))
        )

        assert entity.item_order_code_1 == ""
        assert entity.item_order_code_2 is None
        assert entity.item_specification == "1.0037 | Round bar"

    async def test_virtual_line_is_the_only_one_that_stores_its_own_name(self, db):
        _order(db)
        entity = order_item_orm_to_entity(
            await _loaded(
                db,
                await _order_item(
                    db, line_type="VIRTUAL", virtual_name="Crating and export packing"
                ),
            )
        )

        assert entity.item_article_name == "Crating and export packing"
        assert entity.virtual_name == "Crating and export packing"
        assert entity.bought_item_id is None
        assert entity.made_item_id is None


class TestOrderSearch:
    """A MADE line's name lives in made_item_table, not on the order item,
    so order search has to reach it through the lot position. Without that
    join these orders become unfindable by the name users actually see."""

    @pytest.mark.parametrize(
        "term",
        ["Bracket", "bracket, welded", "LOT-2026-0001"],
        ids=["article-name", "case-insensitive", "lot-number"],
    )
    async def test_finds_an_order_by_its_made_lines_identity(self, db, term):
        await _made_item_line(db)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(OrderFilterDto(search=term))

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_does_not_match_an_unrelated_term(self, db):
        await _made_item_line(db)

        total, _ = await SqlAlchemyOrderRepository(db).get_multi(OrderFilterDto(search="flange"))

        assert total == 0

    async def test_still_finds_a_virtual_line_by_its_own_name(self, db):
        _order(db)
        await _order_item(db, line_type="VIRTUAL", virtual_name="Crating and export packing")

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(search="crating")
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_finds_an_order_by_its_source_lines_order_code(self, db):
        db.add(
            SourceItemTypeOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                name={"enGB": "Round bar"},
                label_color="#000000",
                label_font_color="#ffffff",
                description={},
                creator_id=1,
            )
        )
        db.add(
            SourceItemOrmModel(
                id=1,
                created=NOW,
                changed=NOW,
                changes=[],
                archived=False,
                dimension="40x40x4",
                material="1.0037",
                type_id=1,
                order_code_1="ACME-1234",
                creator_id=1,
            )
        )
        _order(db)
        await _order_item(db, line_type="SOURCE", source_item_id=1)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(OrderFilterDto(search="acme"))

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_finds_an_order_by_its_suppliers_name(self, db):
        """The order pickers search on the server and show the supplier
        beside the number, so the supplier's name finds its orders."""
        await seed_supplier(db)
        _order(db)
        await db.commit()

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(search="supplier 1")
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]
