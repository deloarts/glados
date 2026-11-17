"""
Every lifecycle response carries `actions` over real HTTP: the actions the
reading user may take now, from the aggregate's intent table. Read routes
and mutation routes both fill them.
"""

from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration.test_api_production_state_machine import _seed_lot_with_internal_order
from tests.integration.test_api_production_state_machine import _seed_production_settings  # noqa: F401  (autouse: seeds the production settings)

ORDERS = f"{API_WEB}/orders"
LOTS = f"{API_WEB}/production-lots"
PRODUCTION_ORDERS = f"{API_WEB}/production-orders"


async def test_a_production_order_read_and_started_carries_its_actions(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
    _, _, order = await _seed_lot_with_internal_order(db, 1, with_machine=True)

    read = (await client.get(f"{PRODUCTION_ORDERS}/{order.id}")).json()
    assert read["actions"] == ["start", "cancel", "split", "merge"]
    assert read["can_start"] is True

    started = await client.post(f"{PRODUCTION_ORDERS}/{order.id}/start", json={})
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "in_progress"
    # The reversal is offered on state alone; manage:production_orders is checked
    # by the use case and the client shows the button disabled without it.
    assert body["actions"] == [
        "pause",
        "cancel",
        "record_completion",
        "reverse_completion",
        "scrap",
    ]
    assert body["can_start"] is False


async def test_a_lot_read_carries_its_positions_and_production_orders_actions(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    lot, position, order = await _seed_lot_with_internal_order(db, 1, with_machine=True)

    body = (await client.get(f"{LOTS}/{lot.id}")).json()

    assert "hold" in body["actions"]
    assert "cancel" in body["actions"]
    # Nothing produced yet, so a manager may cancel but not force-complete.
    assert "force_complete" not in body["actions"]
    position_body = next(p for p in body["positions"] if p["id"] == position.id)
    assert position_body["actions"] == []
    order_body = next(o for o in position_body["production_orders"] if o["id"] == order.id)
    assert order_body["actions"] == ["start", "cancel", "split", "merge"]


async def test_a_lot_without_manage_lots_offers_no_cancel(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    lot, _, _ = await _seed_lot_with_internal_order(db, 1)

    body = (await client.get(f"{LOTS}/{lot.id}")).json()

    assert "cancel" not in body["actions"]
    assert "hold" in body["actions"]


async def test_the_lots_list_carries_the_lot_actions(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    lot, _, _ = await _seed_lot_with_internal_order(
        db, 1, lot_status=LotStatus.DRAFT, position_kind=LotPositionKind.UNASSIGNED
    )

    body = (await client.get(f"{LOTS}/", params={"ids": [lot.id]})).json()

    row = next(item for item in body["items"] if item["id"] == lot.id)
    assert row["actions"] == [
        "scrap",
        "edit_structure",
        "reorder_positions",
        "edit_quantity",
        "switch_source",
    ]


async def test_an_order_and_its_lines_carry_their_actions_on_read_and_on_mark(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_ORDERS])
    purchase = await seed.order(db, "draft")
    line = await seed.line(db, purchase, "pending")
    await db.commit()

    read = (await client.get(f"{ORDERS}/{purchase.id}")).json()
    assert read["actions"] == ["mark_requested", "mark_ordered", "cancel", "edit", "add_item"]
    assert read["items"][0]["actions"] == [
        "mark_requested",
        "mark_ordered",
        "cancel",
        "edit_quantity",
        "edit",
        "move",
        "remove",
    ]

    marked = await client.put(f"{ORDERS}/{purchase.id}/items/{line.id}/mark-ordered")
    assert marked.status_code == 200
    # Its only line ordered, the order now reads ordered: changing the line,
    # its pickup readiness included, needs manage:orders, so a writer keeps
    # only the delivery.
    assert marked.json()["actions"] == ["deliver"]


async def test_a_manager_may_still_change_a_line_of_a_submitted_order(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
    purchase = await seed.order(db, "draft")
    line = await seed.line(db, purchase, "pending")
    await db.commit()

    marked = await client.put(f"{ORDERS}/{purchase.id}/items/{line.id}/mark-ordered")

    assert marked.json()["actions"] == [
        "mark_ready_for_pickup",
        "deliver",
        "cancel",
        "edit_quantity",
        "edit",
        "move",
    ]


async def test_a_bought_demand_without_allocations_offers_its_deletion(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_DEMAND_ITEMS])
    demand = await seed.bought_demand(db, "open", None, 3.0)
    await db.commit()

    body = (await client.get(f"{API_WEB}/bought-items-demands/{demand.id}")).json()

    assert body["actions"] == ["cancel", "fulfil", "allocate", "edit_quantity", "remove"]


async def test_a_writer_sees_the_cancel_of_a_submitted_order_blocked_and_is_still_refused(
    db, auth_client
):
    """Past REQUESTED a cancel needs manage:orders. A writer gets it as a
    blocked action naming that permission, and the route still refuses it."""
    client = await auth_client(permissions=[Permission.WRITE_ORDERS])
    purchase = await seed.order(db, "draft")
    line = await seed.line(db, purchase, "pending")
    await db.commit()
    marked = await client.put(f"{ORDERS}/{purchase.id}/items/{line.id}/mark-ordered")
    assert marked.status_code == 200

    read = (await client.get(f"{ORDERS}/{purchase.id}")).json()
    assert "cancel" not in read["actions"]
    assert read["blocked_actions"] == {
        "cancel": Permission.MANAGE_ORDERS,
        "edit": Permission.MANAGE_ORDERS,
        "add_item": Permission.MANAGE_ORDERS,
    }
    assert read["items"][0]["blocked_actions"]["cancel"] == Permission.MANAGE_ORDERS

    refused = await client.put(
        f"{ORDERS}/{purchase.id}/cancel",
        params={"expected_edit_version": read["edit_version"]},
    )
    assert refused.status_code == 403


async def test_a_lot_without_manage_lots_carries_its_cancel_as_blocked(db, auth_client):
    client = await auth_client(permissions=[Permission.WRITE_LOTS])
    lot, _, _ = await _seed_lot_with_internal_order(db, 1)

    body = (await client.get(f"{LOTS}/{lot.id}")).json()
    listed = (await client.get(f"{LOTS}/", params={"ids": [lot.id]})).json()

    assert body["blocked_actions"] == {"cancel": Permission.MANAGE_LOTS}
    row = next(item for item in listed["items"] if item["id"] == lot.id)
    assert row["blocked_actions"] == {"cancel": Permission.MANAGE_LOTS}
