"""
A quote request line stays awarded only while the order line its award
created is live. Canceling or removing that order line, or canceling its
order, opens the request line again with the award fields kept as the
record, so the request goes back to waiting for an award and the line can
be awarded anew. A request closed only because every line was dropped takes
a dropped line back; a request whose lines vanish with a deleted lot
position is derived again. A request someone closed stays closed when an
award on it is voided, notes the void in its changelog and offers a reopen,
which derives its status again from the lines.
"""

from dataclasses import replace
from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository import (
    SqlAlchemyQuoteRequestRepository,
)
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardQuoteRequest,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import line_version
from tests.integration.repository_reads._graph import Graph

RFQ = f"{API_WEB}/quote-requests"
ORDERS = f"{API_WEB}/orders"
LOTS = f"{API_WEB}/production-lots"
BUYER = [
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def buyer(auth_client: Any) -> Any:
    return await auth_client(username="buyer", email="buyer@example.com", permissions=BUYER)


async def _open_demand(graph: Graph, quantity: float) -> int:
    template = await graph.bought_demand()
    saved = await SqlAlchemyBoughtItemDemandItemRepository(graph.db).save(
        replace(template, id=0, quantity=quantity, status=BoughtItemDemandStatus.OPEN, changes=[])
    )
    await graph.db.commit()
    return saved.id


async def _bought_line(graph: Graph, demand_id: int) -> dict:
    return {
        "bought_item_id": (await graph.bought_item()).id,
        "project_id": (await graph.project()).id,
        "quantity": 2.0,
        "unit": "pcs",
        "demands": [{"family": "bought", "demand_item_id": demand_id, "quantity": 2.0}],
    }


async def _sent_request(buyer: Any, graph: Graph, lines: list[dict]) -> dict:
    acme = await graph.supplier()
    created = await buyer.post(f"{RFQ}/", json={"supplier_ids": [acme.id], "lines": lines})
    assert created.status_code == 201, created.text
    request = created.json()
    row = request["suppliers"][0]
    sent = await buyer.post(f"{RFQ}/{request['id']}/suppliers/{row['id']}/sent")
    assert sent.status_code == 200, sent.text
    return dict(sent.json())


async def _award(buyer: Any, request_id: int, line_id: int, row_id: int) -> Any:
    fresh = (await buyer.get(f"{RFQ}/{request_id}")).json()
    return await buyer.post(
        f"{RFQ}/{request_id}/award",
        json={
            "awards": [{"line_id": line_id, "supplier_row_id": row_id}],
            "expected_edit_version": fresh["edit_version"],
        },
    )


async def _awarded(buyer: Any, graph: Graph) -> tuple[dict, int, dict]:
    """A sent request whose only line was awarded; returns the request, the
    demand and the order line the award created, with its order's number."""
    demand = await _open_demand(graph, 2.0)
    request = await _sent_request(buyer, graph, [await _bought_line(graph, demand)])
    line_id = request["lines"][0]["id"]
    awarded = await _award(buyer, request["id"], line_id, request["suppliers"][0]["id"])
    assert awarded.status_code == 200, awarded.text
    assert awarded.json()["request"]["status"] == "awarded"
    order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    return request, demand, {**order["items"][0], "order_number": order["order_number"]}


async def _open_links(buyer: Any, demand: int) -> list[str]:
    links = (await buyer.get(f"{RFQ}/open-links", params={"bought_demand_ids": [demand]})).json()
    return [r["request_number"] for r in links["bought_demands"].get(str(demand), [])]


async def test_canceling_the_awarded_order_line_opens_the_request_line_again(
    graph: Graph, buyer: Any
) -> None:
    request, demand, item = await _awarded(buyer, graph)

    canceled = await buyer.post(
        f"{ORDERS}/{item['order_id']}/items/{item['id']}/cancel",
        params={"expected_edit_version": item["edit_version"]},
    )

    assert canceled.status_code == 200, canceled.text
    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert after["status"] == "sent"
    [line] = after["lines"]
    assert line["state"] == "open"
    assert line["award_voided"] is True
    assert line["awarded_supplier_id"] == request["suppliers"][0]["id"]
    assert line["order_number"] == item["order_number"]
    assert "award" in after["actions"]
    assert await _open_links(buyer, demand) == [request["request_number"]]

    again = await _award(buyer, request["id"], line["id"], request["suppliers"][0]["id"])

    assert again.status_code == 200, again.text
    [reawarded] = again.json()["request"]["lines"]
    assert reawarded["state"] == "awarded"
    assert reawarded["award_voided"] is False
    assert again.json()["request"]["status"] == "awarded"


async def test_canceling_the_order_reopens_the_lines_it_was_awarded_from(
    graph: Graph, buyer: Any
) -> None:
    request, _demand, item = await _awarded(buyer, graph)
    order = (await buyer.get(f"{ORDERS}/{item['order_id']}")).json()

    canceled = await buyer.put(
        f"{ORDERS}/{order['id']}/cancel", params={"expected_edit_version": order["edit_version"]}
    )

    assert canceled.status_code == 200, canceled.text
    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert after["status"] == "sent"
    assert [(line["state"], line["award_voided"]) for line in after["lines"]] == [("open", True)]


async def test_removing_the_awarded_order_line_opens_the_request_line_again(
    graph: Graph, buyer: Any
) -> None:
    request, _demand, item = await _awarded(buyer, graph)

    removed = await buyer.delete(
        f"{ORDERS}/{item['order_id']}/items/{item['id']}",
        params={"expected_edit_version": await line_version(buyer, item["order_id"], item["id"])},
    )

    assert removed.status_code == 204, removed.text
    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert after["status"] == "sent"
    [line] = after["lines"]
    assert (line["state"], line["award_voided"], line["order_number"]) == ("open", True, "")


async def test_a_request_closed_by_dropping_every_line_takes_a_line_back(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 2.0)
    request = await _sent_request(buyer, graph, [await _bought_line(graph, demand)])
    line_id = request["lines"][0]["id"]

    dropped = await buyer.post(f"{RFQ}/{request['id']}/lines/{line_id}/drop")
    restored = await buyer.post(f"{RFQ}/{request['id']}/lines/{line_id}/restore")

    assert dropped.json()["status"] == "closed"
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "sent"
    assert [line["state"] for line in restored.json()["lines"]] == ["open"]


async def test_a_request_that_reads_awarded_takes_a_line_dropped_by_mistake_back(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 4.0)
    request = await _sent_request(
        buyer, graph, [await _bought_line(graph, demand), await _bought_line(graph, demand)]
    )
    first, second = request["lines"]
    await buyer.post(f"{RFQ}/{request['id']}/lines/{second['id']}/drop")
    await _award(buyer, request["id"], first["id"], request["suppliers"][0]["id"])
    assert (await buyer.get(f"{RFQ}/{request['id']}")).json()["status"] == "awarded"

    restored = await buyer.post(f"{RFQ}/{request['id']}/lines/{second['id']}/restore")

    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "sent"
    assert sorted(line["state"] for line in restored.json()["lines"]) == ["awarded", "open"]


async def test_an_explicitly_closed_request_takes_no_line_back(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 4.0)
    request = await _sent_request(
        buyer, graph, [await _bought_line(graph, demand), await _bought_line(graph, demand)]
    )
    first, second = request["lines"]
    await _award(buyer, request["id"], first["id"], request["suppliers"][0]["id"])
    current = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    closed = await buyer.post(
        f"{RFQ}/{request['id']}/close", params={"expected_edit_version": current["edit_version"]}
    )
    assert closed.status_code == 200, closed.text

    restored = await buyer.post(f"{RFQ}/{request['id']}/lines/{second['id']}/restore")

    assert restored.status_code == 409


async def test_deleting_a_lot_position_derives_the_requests_naming_it_again(
    graph: Graph, buyer: Any
) -> None:
    position = await graph.internal_position()
    demand = await _open_demand(graph, 2.0)
    request = await _sent_request(
        buyer,
        graph,
        [
            {"lot_position_id": position.id, "quantity": 4.0, "unit": "pcs"},
            await _bought_line(graph, demand),
        ],
    )
    made_line, bought_line = request["lines"]
    dropped = await buyer.post(f"{RFQ}/{request['id']}/lines/{bought_line['id']}/drop")
    assert dropped.json()["status"] == "sent"
    [step] = [
        s
        for s in await SqlAlchemyProductionLotRepository(graph.db).get_steps(position.lot_id)
        if s.position_id == position.id
    ]

    deleted = await buyer.delete(f"{LOTS}/{position.lot_id}/steps/{step.id}")

    assert deleted.status_code == 204, deleted.text
    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert [line["id"] for line in after["lines"]] == [bought_line["id"]]
    assert after["status"] == "closed"
    assert made_line["id"] not in {line["id"] for line in after["lines"]}


async def test_an_award_refuses_a_request_changed_before_its_lock(
    graph: Graph, buyer: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    demand = await _open_demand(graph, 2.0)
    request = await _sent_request(buyer, graph, [await _bought_line(graph, demand)])
    line_id = request["lines"][0]["id"]
    row_id = request["suppliers"][0]["id"]
    checks = AwardQuoteRequest._check_before_locks

    async def offer_changes_meanwhile(self: AwardQuoteRequest, placements: Any) -> None:
        # A second writer records a new price between the award's first read
        # and its lock, as a concurrent request would.
        changed = await buyer.put(
            f"{RFQ}/{request['id']}/suppliers/{row_id}/offer",
            json={"quotes": [{"line_id": line_id, "unit_price": 999}]},
        )
        assert changed.status_code == 200, changed.text
        await checks(self, placements)

    monkeypatch.setattr(AwardQuoteRequest, "_check_before_locks", offer_changes_meanwhile)

    refused = await _award(buyer, request["id"], line_id, row_id)

    assert refused.status_code == 409, refused.text
    assert "changed while the award was prepared" in refused.text


# ── A voided award on a closed request, and the reopen ────────────────────


async def _close(buyer: Any, request_id: int) -> dict:
    current = (await buyer.get(f"{RFQ}/{request_id}")).json()
    closed = await buyer.post(
        f"{RFQ}/{request_id}/close", params={"expected_edit_version": current["edit_version"]}
    )
    assert closed.status_code == 200, closed.text
    return dict(closed.json())


async def _reopen(client: Any, request_id: int, edit_version: int | None = None) -> Any:
    if edit_version is None:
        edit_version = (await client.get(f"{RFQ}/{request_id}")).json()["edit_version"]
    return await client.post(
        f"{RFQ}/{request_id}/reopen", params={"expected_edit_version": edit_version}
    )


async def _changelog(graph: Graph, request_id: int) -> list[str]:
    request = await SqlAlchemyQuoteRequestRepository(graph.db).get_by_id(request_id)
    assert request is not None
    return request.changes


async def _closed_after_award(buyer: Any, graph: Graph, *, sent: bool = True) -> tuple[dict, dict]:
    """A request with two quoted lines, the first awarded and the second
    dropped by the close; returns the request as created and the order line
    the award created, with its order's number."""
    demand = await _open_demand(graph, 4.0)
    lines = [await _bought_line(graph, demand), await _bought_line(graph, demand)]
    if sent:
        request = await _sent_request(buyer, graph, lines)
    else:
        acme = await graph.supplier()
        created = await buyer.post(f"{RFQ}/", json={"supplier_ids": [acme.id], "lines": lines})
        assert created.status_code == 201, created.text
        request = created.json()
    row_id = request["suppliers"][0]["id"]
    offer = await buyer.put(
        f"{RFQ}/{request['id']}/suppliers/{row_id}/offer",
        json={"quotes": [{"line_id": line["id"], "unit_price": 150} for line in request["lines"]]},
    )
    assert offer.status_code == 200, offer.text
    awarded = await _award(buyer, request["id"], request["lines"][0]["id"], row_id)
    assert awarded.status_code == 200, awarded.text
    order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    await _close(buyer, request["id"])
    return request, {**order["items"][0], "order_number": order["order_number"]}


async def _cancel_line(buyer: Any, item: dict) -> None:
    canceled = await buyer.post(
        f"{ORDERS}/{item['order_id']}/items/{item['id']}/cancel",
        params={"expected_edit_version": item["edit_version"]},
    )
    assert canceled.status_code == 200, canceled.text


async def _closed_with_voided_award(buyer: Any, graph: Graph) -> tuple[dict, dict, dict]:
    """A closed request whose award was voided after the close by canceling
    its order line; returns the request as created, the canceled order line
    and the request after the void."""
    request, item = await _closed_after_award(buyer, graph)
    await _cancel_line(buyer, item)
    return request, item, (await buyer.get(f"{RFQ}/{request['id']}")).json()


async def test_a_voided_award_keeps_a_closed_request_closed_and_notes_the_void(
    graph: Graph, buyer: Any
) -> None:
    request, item, after = await _closed_with_voided_award(buyer, graph)

    assert after["status"] == "closed"
    assert after["closed_at"] is not None
    assert [(line["state"], line["award_voided"]) for line in after["lines"]] == [
        ("open", True),
        ("dropped", False),
    ]
    assert after["actions"] == ["reopen"]
    changes = await _changelog(graph, request["id"])
    assert changes[-1].endswith(
        f"Award of line 1 to {request['suppliers'][0]['supplier_name']} voided: "
        f"its line on order {item['order_number']} was canceled."
    )
    assert "Status:" not in changes[-1]


async def test_removing_the_order_line_of_a_closed_request_notes_the_void(
    graph: Graph, buyer: Any
) -> None:
    request, item = await _closed_after_award(buyer, graph)

    removed = await buyer.delete(
        f"{ORDERS}/{item['order_id']}/items/{item['id']}",
        params={"expected_edit_version": await line_version(buyer, item["order_id"], item["id"])},
    )

    assert removed.status_code == 204, removed.text
    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert after["status"] == "closed"
    assert after["actions"] == ["reopen"]
    assert (await _changelog(graph, request["id"]))[-1].endswith(
        "voided: its order line was removed."
    )


async def test_a_void_that_keeps_the_status_still_notes_it(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 4.0)
    request = await _sent_request(
        buyer, graph, [await _bought_line(graph, demand), await _bought_line(graph, demand)]
    )
    first = request["lines"][0]
    awarded = await _award(buyer, request["id"], first["id"], request["suppliers"][0]["id"])
    assert awarded.json()["request"]["status"] == "sent"
    order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    [item] = order["items"]

    await _cancel_line(buyer, item)

    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert after["status"] == "sent"
    assert "reopen" not in after["actions"]
    changes = await _changelog(graph, request["id"])
    assert sum("voided" in change for change in changes) == 1
    assert changes[-1].endswith(f"its line on order {order['order_number']} was canceled.")


async def test_reopen_clears_the_close_and_derives_the_status_again(
    graph: Graph, buyer: Any
) -> None:
    request, _item, closed = await _closed_with_voided_award(buyer, graph)
    voided, dropped = closed["lines"]

    reopened = await _reopen(buyer, request["id"], closed["edit_version"])

    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["status"] == "sent"
    assert body["closed_at"] is None
    assert body["edit_version"] == closed["edit_version"] + 1
    assert [line["state"] for line in body["lines"]] == ["open", "dropped"]
    assert [q["unit_price"] for q in body["suppliers"][0]["quotes"]] == [150, 150]
    assert "award" in body["actions"]
    assert "reopen" not in body["actions"]
    changes = await _changelog(graph, request["id"])
    assert changes[-2].endswith("Quote request reopened.")
    assert changes[-1].endswith("Status: closed → sent (Quote request reopened).")

    restored = await buyer.post(f"{RFQ}/{request['id']}/lines/{dropped['id']}/restore")
    again = await _award(buyer, request["id"], voided["id"], request["suppliers"][0]["id"])

    assert restored.status_code == 200, restored.text
    assert again.status_code == 200, again.text
    assert [line["state"] for line in again.json()["request"]["lines"]] == ["awarded", "open"]


async def test_reopen_derives_draft_for_a_request_never_sent(graph: Graph, buyer: Any) -> None:
    request, item = await _closed_after_award(buyer, graph, sent=False)
    await _cancel_line(buyer, item)

    reopened = await _reopen(buyer, request["id"])

    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "draft"


async def test_reopen_refuses_a_closed_request_without_a_voided_line(
    graph: Graph, buyer: Any
) -> None:
    request, _item = await _closed_after_award(buyer, graph)
    closed = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert closed["status"] == "closed"
    assert "reopen" not in closed["actions"]

    refused = await _reopen(buyer, request["id"], closed["edit_version"])

    assert refused.status_code == 409, refused.text
    assert "a line whose award was voided" in refused.text


async def test_reopen_refuses_an_open_request(graph: Graph, buyer: Any) -> None:
    request, _demand, item = await _awarded(buyer, graph)
    await _cancel_line(buyer, item)
    after = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert after["status"] == "sent"
    assert "reopen" not in after["actions"]

    refused = await _reopen(buyer, request["id"], after["edit_version"])

    assert refused.status_code == 409, refused.text


async def test_reopen_refuses_a_canceled_request(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 2.0)
    request = await _sent_request(buyer, graph, [await _bought_line(graph, demand)])
    canceled = await buyer.post(
        f"{RFQ}/{request['id']}/cancel", params={"expected_edit_version": request["edit_version"]}
    )
    assert canceled.status_code == 200, canceled.text
    assert "reopen" not in canceled.json()["actions"]

    refused = await _reopen(buyer, request["id"], canceled.json()["edit_version"])

    assert refused.status_code == 409, refused.text


async def test_reopen_checks_the_edit_version(graph: Graph, buyer: Any) -> None:
    request, _item, closed = await _closed_with_voided_award(buyer, graph)

    refused = await _reopen(buyer, request["id"], closed["edit_version"] - 1)

    assert refused.status_code == 409, refused.text
    assert (await buyer.get(f"{RFQ}/{request['id']}")).json()["status"] == "closed"


async def test_reopen_needs_the_permission_to_change_quote_requests(
    graph: Graph, buyer: Any, auth_client: Any
) -> None:
    request, _item, closed = await _closed_with_voided_award(buyer, graph)
    reader = await auth_client(username="reader", email="reader@example.com", permissions=[])

    refused = await _reopen(reader, request["id"], closed["edit_version"])

    assert refused.status_code == 403, refused.text
    assert (await buyer.get(f"{RFQ}/{request['id']}")).json()["status"] == "closed"
