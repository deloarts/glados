"""
A scrap that takes a lot to zero ends its work the way a lot cancel does:
a supplier line already ordered for a later position stays open, since it
was never canceled with the supplier, and purchasing is told which lines to
settle; the production order that scrapped its whole quantity ends
completed, as everything it processed, not canceled.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import production_order_version
from tests.integration.test_api_lifecycle_scenarios import SUPPLIER_ORDERS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import ORDERS
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def test_a_lot_scrapped_to_zero_keeps_its_ordered_supplier_line_open(
    db: AsyncSession, auth_client: Any, published_events: list[object]
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    order = await shop.production_order(first, 10.0, 1)
    assigned = await shop.assign_external(second)
    assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(second)
    submitted = await shop.client.put(f"{SUPPLIER_ORDERS}/{shop.order_id}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    started = await shop.client.post(f"{ORDERS}/{order}/start", json={})
    assert started.status_code == 200, started.text
    published_events.clear()

    scrapped = await shop.client.post(
        f"{ORDERS}/{order}/scrap",
        json={
            "quantity": 10.0,
            "reason": "tool_breakage",
            "create_replacement": False,
            "expected_edit_version": await production_order_version(shop.client, order),
            "expected_lot_edit_version": await lot_version(shop.client, shop.floor.lot_id),
        },
    )

    assert scrapped.status_code == 200, scrapped.text
    table = await shop.table()
    assert table["lot"] == "scrapped"
    assert table[f"line{line}"] == "ordered"
    assert table["order"] != "canceled"
    assert table[f"production_order{order}"] == "completed"
    notices = [e for e in published_events if isinstance(e, LotSupplierLinesToSettle)]
    assert [n.ended for n in notices] == ["scrapped"]
    assert notices[0].open_lines
