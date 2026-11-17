"""
Reversing a completion through the API: the reversal books the original's
pieces negative and names it, the order's completed count drops, and both
rows stay. A completion is reversed once, a reversal is not reversed, the
reason is required and the action needs manage:production_orders. While the lot
is on hold, a reversal, a completion and a scrap wait for its resume, and
pieces provided to the supplier of an external next position stay used.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import update

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
    ProductionOrderCompletionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import lot_version
from tests.integration._lot_facts import _SEEDER
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

ORDERS = f"{API_WEB}/production-orders"
REVERSER = [Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="operator", email="operator@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def reverser(auth_client: Any) -> Any:
    return await auth_client(username="lead", email="lead@example.com", permissions=REVERSER)


async def _completed_two(graph: Graph) -> tuple[int, int]:
    """The graph's running order of 10 with one completion of 2 accepted
    pieces, its stored completed count matching."""
    completion = await graph.completion()
    orders = SqlAlchemyProductionOrderRepository(graph.db)
    order = await orders.get_by_id(completion.production_order_id)
    assert order is not None
    order.quantity_completed = 2.0
    await orders.save(order)
    await graph.db.commit()
    await graph._settle_lot()
    return order.id, completion.id


async def _reverse(client: Any, order_id: int, completion_id: int, reason: str = "Miscounted"):
    return await client.post(
        f"{ORDERS}/{order_id}/completions/{completion_id}/reverse", json={"reason": reason}
    )


async def test_a_reversal_books_the_pieces_negative_and_keeps_both_rows(
    graph: Graph, reverser: Any
) -> None:
    order_id, completion_id = await _completed_two(graph)

    response = await _reverse(reverser, order_id, completion_id)

    assert response.status_code == 200, response.text
    order = response.json()
    assert order["quantity_completed"] == 0.0
    assert order["status"] == "in_progress"
    rows = {c["id"]: c for c in order["completions"]}
    [reversal] = [c for c in rows.values() if c["reverses_completion_id"] == completion_id]
    assert (reversal["quantity"], reversal["quantity_accepted"]) == (-2.0, -2.0)
    assert reversal["note"] == "Miscounted"
    assert rows[completion_id]["quantity"] == 2.0


async def test_a_completion_is_reversed_once_and_a_reversal_never(
    graph: Graph, reverser: Any
) -> None:
    order_id, completion_id = await _completed_two(graph)
    first = await _reverse(reverser, order_id, completion_id)
    reversal_id = next(c["id"] for c in first.json()["completions"] if c["reverses_completion_id"])

    again = await _reverse(reverser, order_id, completion_id)
    of_reversal = await _reverse(reverser, order_id, reversal_id)

    assert again.status_code == 409, again.text
    assert again.json()["code"] == "CompletionAlreadyReversedError"
    assert of_reversal.status_code == 409, of_reversal.text
    assert of_reversal.json()["code"] == "CompletionNotReversibleError"


async def test_the_reason_is_required(graph: Graph, reverser: Any) -> None:
    order_id, completion_id = await _completed_two(graph)

    response = await _reverse(reverser, order_id, completion_id, reason="   ")

    assert response.status_code == 422, response.text


async def test_reversing_needs_its_own_permission(graph: Graph, auth_client: Any) -> None:
    order_id, completion_id = await _completed_two(graph)
    operator = await auth_client(
        username="worker",
        email="worker@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )

    response = await _reverse(operator, order_id, completion_id)

    assert response.status_code == 403, response.text


async def test_the_order_shows_what_it_processed_and_what_is_left(
    graph: Graph, reverser: Any
) -> None:
    order_id, completion_id = await _completed_two(graph)

    before = (await reverser.get(f"{ORDERS}/{order_id}")).json()
    after = (await _reverse(reverser, order_id, completion_id)).json()

    assert (before["quantity_processed"], before["quantity_open"]) == (2.0, 8.0)
    assert (after["quantity_processed"], after["quantity_open"]) == (0.0, 10.0)


async def test_a_reversal_keeps_the_machine_of_the_batch_it_takes_back(
    graph: Graph, reverser: Any
) -> None:
    order_id, completion_id = await _completed_two(graph)
    machine = await graph.machine()
    await graph.db.execute(
        update(ProductionOrderCompletionOrmModel)
        .where(ProductionOrderCompletionOrmModel.id == completion_id)
        .values(machine_id=machine.id)
    )
    await graph.db.commit()

    response = await _reverse(reverser, order_id, completion_id)

    assert response.status_code == 200, response.text
    [reversal] = [c for c in response.json()["completions"] if c["reverses_completion_id"]]
    assert reversal["machine_id"] == machine.id


_LOTS = f"{API_WEB}/production-lots"


class _NoBus:
    async def publish(self, event: object) -> None:
        return None


_LEAD = [*REVERSER, Permission.WRITE_LOTS, Permission.MANAGE_LOTS]


async def _held(graph: Graph, client: Any) -> int:
    """Holds the graph's lot, which pauses its running order, and returns
    the lot id."""
    lot = await graph.lot()
    held = await client.post(f"{_LOTS}/{lot.id}/hold", json={"reason": "Material check"})
    assert held.status_code == 200, held.text
    return lot.id


async def test_a_reversal_on_a_held_lot_waits_until_the_lot_resumes(
    graph: Graph, auth_client: Any
) -> None:
    lead = await auth_client(username="lead", email="lead@example.com", permissions=_LEAD)
    order_id, completion_id = await _completed_two(graph)
    lot_id = await _held(graph, lead)

    refused = await _reverse(lead, order_id, completion_id)
    order = (await lead.get(f"{ORDERS}/{order_id}")).json()
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "LotOnHoldError"
    assert (order["status"], order["quantity_completed"]) == ("paused", 2.0)

    resumed = await lead.post(f"{_LOTS}/{lot_id}/resume")
    assert resumed.status_code == 200, resumed.text
    reversed_ = await _reverse(lead, order_id, completion_id)
    assert reversed_.status_code == 200, reversed_.text
    assert reversed_.json()["status"] == "in_progress"


async def test_a_completion_and_a_scrap_on_a_held_lot_are_refused(
    graph: Graph, auth_client: Any
) -> None:
    lead = await auth_client(username="lead", email="lead@example.com", permissions=_LEAD)
    order_id, _ = await _completed_two(graph)
    lot_id = await _held(graph, lead)
    # A running order under the held lot, as one that a hold found completed
    # and that came back to work since: its hold interruption is closed.
    await graph.db.execute(
        update(ProductionOrderInterruptionOrmModel)
        .where(ProductionOrderInterruptionOrmModel.production_order_id == order_id)
        .values(resumed_at=datetime.now(UTC))
    )
    await graph.db.commit()
    reconciler = LifecycleReconciler(sql_lifecycle_repositories(graph.db), _NoBus())
    reconciler.touch_production_orders([order_id])
    await reconciler.run(_SEEDER, datetime.now(UTC), reason="seeded")
    await graph.db.commit()
    order = (await lead.get(f"{ORDERS}/{order_id}")).json()
    assert order["status"] == "in_progress"
    assert {"record_completion", "scrap"}.isdisjoint(order["actions"])

    completion = await lead.post(
        f"{ORDERS}/{order_id}/completions",
        json={"quantity": 1, "completion_date": datetime.now(UTC).date().isoformat()},
    )
    scrap = await lead.post(
        f"{ORDERS}/{order_id}/scrap",
        json={
            "quantity": 1,
            "reason": "tool_breakage",
            "create_replacement": False,
            "expected_edit_version": order["edit_version"],
            "expected_lot_edit_version": await lot_version(lead, lot_id),
        },
    )

    assert completion.status_code == 409, completion.text
    assert completion.json()["code"] == "LotOnHoldError"
    assert scrap.status_code == 409, scrap.text
    assert scrap.json()["code"] == "LotOnHoldError"
    after = (await lead.get(f"{ORDERS}/{order_id}")).json()
    assert after["quantity_completed"] == 2.0


async def test_a_reversal_of_pieces_provided_to_the_next_supplier_is_refused(
    graph: Graph, reverser: Any
) -> None:
    order_id, completion_id = await _completed_two(graph)
    successor = await graph.external_position()
    await SqlAlchemyProductionLotRepository(graph.db).save_provision(
        make(LotPositionProvision, lot_position_id=successor.id, quantity=2.0, creator_id=1)
    )
    await graph.db.commit()

    refused = await _reverse(reverser, order_id, completion_id)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "CompletionNotReversibleError"
    order = (await reverser.get(f"{ORDERS}/{order_id}")).json()
    assert order["quantity_completed"] == 2.0


async def test_a_finished_lot_neither_offers_nor_takes_a_reversal(
    graph: Graph, auth_client: Any
) -> None:
    lead = await auth_client(username="lead", email="lead@example.com", permissions=_LEAD)
    order_id, completion_id = await _completed_two(graph)
    lot = await graph.lot()
    completed = await lead.post(
        f"{_LOTS}/{lot.id}/complete",
        json={"reason": "Enough", "expected_edit_version": await lot_version(lead, lot.id)},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    order = (await lead.get(f"{ORDERS}/{order_id}")).json()
    refused = await _reverse(lead, order_id, completion_id)

    assert "reverse_completion" not in order["actions"]
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "CompletionNotReversibleError"


async def test_a_user_without_the_permission_is_offered_the_reversal_but_refused(
    graph: Graph, auth_client: Any
) -> None:
    order_id, completion_id = await _completed_two(graph)
    operator = await auth_client(
        username="worker",
        email="worker@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )

    order = (await operator.get(f"{ORDERS}/{order_id}")).json()
    refused = await _reverse(operator, order_id, completion_id)

    assert "reverse_completion" in order["actions"]
    assert refused.status_code == 403, refused.text


async def test_a_completed_order_in_a_running_lot_offers_the_reversal(
    graph: Graph, auth_client: Any
) -> None:
    """A completed order has no scheduling context, yet the intent table
    allows reversing its completion while the lot runs, so the lot detail
    lists the action even for a user who lacks the permission."""
    order_id, _ = await _completed_two(graph)
    orders = SqlAlchemyProductionOrderRepository(graph.db)
    order = await orders.get_by_id(order_id)
    assert order is not None
    # The order processed all it was asked for, so it derives completed.
    order.quantity = 2.0
    order.status = ProductionOrderStatus.COMPLETED
    order.actual_end = datetime.now(UTC)
    await orders.save(order)
    await graph.db.commit()
    await graph._settle_lot()
    lot = await graph.lot()
    operator = await auth_client(
        username="worker",
        email="worker@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )

    detail = await operator.get(f"{_LOTS}/{lot.id}")

    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["status"] not in {"completed", "canceled"}
    listed = [o for p in body["positions"] for o in p["production_orders"] if o["id"] == order_id]
    assert listed and listed[0]["status"] == "completed"
    assert "reverse_completion" in listed[0]["actions"]
