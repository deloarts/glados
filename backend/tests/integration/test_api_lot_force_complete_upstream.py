"""
A lot whose good pieces sit only at an earlier position, because its last
step cannot be done, can still end: cancel stays refused, since it would
throw the good pieces away, and force-complete closes the lot at what its
last position produced, nothing here, so it reads as scrapped, and
records the upstream pieces as dropped.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration._edit_versions import lot_version
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def test_a_lot_with_good_pieces_only_upstream_is_force_completed_at_nothing(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, _second = await shop.positions()
    order = await shop.production_order(first, 10.0, 1)
    _started, done = await shop.run(order, 5.0)
    assert done.status_code < 300, done.text
    lot_id = shop.floor.lot_id

    canceled = await shop.client.post(
        f"{LOTS}/{lot_id}/cancel",
        json={"expected_edit_version": await lot_version(shop.client, lot_id)},
    )
    completed = await shop.client.post(
        f"{LOTS}/{lot_id}/complete",
        json={"expected_edit_version": await lot_version(shop.client, lot_id)},
    )

    assert canceled.status_code == 422, canceled.text
    assert completed.status_code == 200, completed.text
    lot = (await shop.client.get(f"{LOTS}/{lot_id}")).json()
    # A lot whose quantity is zero reads as scrapped, as after a full scrap.
    assert lot["status"] == "scrapped"
    assert lot["quantity"] == 0.0
    listed = await shop.client.get(f"{LOTS}/{lot_id}/events")
    assert listed.status_code == 200, listed.text
    events = listed.json()
    assert any(event["event_type"] == "wip_dropped" for event in events), events
