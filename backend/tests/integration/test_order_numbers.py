"""
Order numbers come from the order family's counter: a template whose
sequence outgrows its padding keeps counting instead of drawing the same
number again, a prefix with LIKE wildcards matches literally, two draws
never return the same number even before either order is saved, and the
date in the prefix is the tenant's day.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.adapters.outbound.persistence import number_counters
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

_NOW = datetime(2026, 10, 25, 9, tzinfo=UTC)


async def _save_order(graph: Graph, number: str) -> None:
    supplier = await graph.supplier()
    await SqlAlchemyOrderRepository(graph.db).save(
        make(
            Order,
            order_number=number,
            status=OrderStatus.DRAFT,
            created=_NOW,
            creator_id=graph.uid,
            supplier_id=supplier.id,
        )
    )
    await graph.db.commit()


async def test_a_sequence_past_its_padding_keeps_counting(db) -> None:
    graph = await Graph.seed(db)
    for n in range(1, 10):
        await _save_order(graph, f"PO_{n}")
    orders = SqlAlchemyOrderRepository(db)

    tenth = await orders.next_order_number("PO_{seq}")
    await _save_order(graph, tenth)
    eleventh = await orders.next_order_number("PO_{seq}")

    assert (tenth, eleventh) == ("PO_10", "PO_11")


async def test_two_draws_before_any_save_get_distinct_numbers(db) -> None:
    orders = SqlAlchemyOrderRepository(db)

    first = await orders.next_order_number("ORD-{seq:03d}")
    second = await orders.next_order_number("ORD-{seq:03d}")

    assert (first, second) == ("ORD-001", "ORD-002")


async def test_an_underscore_in_the_prefix_matches_only_itself(db) -> None:
    graph = await Graph.seed(db)
    await _save_order(graph, "PXQ7")
    orders = SqlAlchemyOrderRepository(db)

    assert await orders.next_order_number("P_Q{seq}") == "P_Q1"


async def test_the_date_in_the_prefix_is_the_tenants_day(db, monkeypatch) -> None:
    # 23:30 UTC on New Year's Eve is already New Year's Day in Vienna.
    settings = await db.get(AdminGeneralSettingsOrmModel, 1)
    settings.default_timezone = "Europe/Vienna"
    await db.commit()
    monkeypatch.setattr(
        number_counters, "now_utc", lambda: datetime(2026, 12, 31, 23, 30, tzinfo=UTC)
    )

    assert await SqlAlchemyOrderRepository(db).next_order_number("O{year}-{seq}") == "O2027-1"
