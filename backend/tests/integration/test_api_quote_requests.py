"""
Quote requests over HTTP: a request is built from demands with suppliers,
goes out, collects offers, compares them and awards its lines onto draft
orders, allocating the demands then and carrying the offers' extra costs.
A demand share reserves nothing until the award, which cuts it to what the
demand still needs. A MADE line assigns its lot position to the winner. A
request is closed or canceled, and the demand and position tables learn
which open requests ask for them. A line can be replaced by a line for
another item, and a supplier can quote an alternative item; the award then
records the substitution against the demands.
"""

from dataclasses import replace
from typing import Any

import pytest

from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardQuoteRequest,
)
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

RFQ = f"{API_WEB}/quote-requests"
ORDERS = f"{API_WEB}/orders"
BUYER = [Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]


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


async def _second_supplier(graph: Graph, *, archived: bool = False) -> int:
    saved = await SqlAlchemySupplierRepository(graph.db).save(
        make(
            Supplier,
            name="Bolt & Co",
            vat_id="ATU2",
            edp_code="BOL",
            level=SupplierLevel.B,
            capability_ids=[],
            article_group_ids=[],
            creator_id=graph.uid,
            archived=archived,
        )
    )
    await graph.db.commit()
    return saved.id


async def _bought_line(graph: Graph, quantity: float, demand_id: int, share: float) -> dict:
    return {
        "bought_item_id": (await graph.bought_item()).id,
        "project_id": (await graph.project()).id,
        "quantity": quantity,
        "unit": "pcs",
        "demands": [{"family": "bought", "demand_item_id": demand_id, "quantity": share}],
    }


async def _request(buyer: Any, graph: Graph, lines: list[dict], suppliers: list[int]) -> dict:
    created = await buyer.post(f"{RFQ}/", json={"supplier_ids": suppliers, "lines": lines})
    assert created.status_code == 201, created.text
    return dict(created.json())


async def _allocated(buyer: Any, demand_id: int) -> float:
    response = await buyer.get(f"{API_WEB}/bought-items-allocations/demand/{demand_id}")
    assert response.status_code == 200, response.text
    return sum(a["quantity"] for a in response.json())


async def _offer(
    buyer: Any, request: dict, row: dict, prices: dict[int, int], **extra: Any
) -> dict:
    body = {"quotes": [{"line_id": k, "unit_price": v} for k, v in prices.items()], **extra}
    response = await buyer.put(f"{RFQ}/{request['id']}/suppliers/{row['id']}/offer", json=body)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _award(buyer: Any, request: dict, awards: dict[int, int], **extra: Any) -> Any:
    fresh = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    body = {
        "awards": [{"line_id": k, "supplier_row_id": v} for k, v in awards.items()],
        "expected_edit_version": fresh["edit_version"],
        **extra,
    }
    return await buyer.post(f"{RFQ}/{request['id']}/award", json=body)


async def test_quote_request_is_created_from_a_demand_without_allocating_it(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 5.0)
    supplier = await graph.supplier()

    request = await _request(
        buyer, graph, [await _bought_line(graph, 5.0, demand, 5.0)], [supplier.id]
    )

    assert request["status"] == "draft"
    assert request["request_number"].startswith("RFQ-")
    assert [line["state"] for line in request["lines"]] == ["open"]
    assert request["suppliers"][0]["supplier_name"] == "Acme"
    assert "send" in request["actions"]
    assert await _allocated(buyer, demand) == 0.0
    links = (await buyer.get(f"{RFQ}/open-links", params={"bought_demand_ids": [demand]})).json()
    assert [r["request_number"] for r in links["bought_demands"][str(demand)]] == [
        request["request_number"]
    ]


async def test_quote_request_line_for_another_item_than_its_demand_is_refused(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 5.0)
    line = await _bought_line(graph, 5.0, demand, 5.0)
    line["demands"][0]["quantity"] = 6.0

    refused = await buyer.post(f"{RFQ}/", json={"lines": [line]})

    assert refused.status_code == 422
    assert refused.json()["code"] == "QuoteRequestInvalidError"


async def test_quote_request_compares_offers_and_awards_per_line(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 4.0)
    acme = await graph.supplier()
    bolt = await _second_supplier(graph)
    request = await _request(
        buyer, graph, [await _bought_line(graph, 4.0, demand, 4.0)], [acme.id, bolt]
    )
    line_id = request["lines"][0]["id"]
    acme_row, bolt_row = request["suppliers"]
    sent = await buyer.post(f"{RFQ}/{request['id']}/suppliers/{acme_row['id']}/sent")
    assert sent.json()["status"] == "sent"
    await _offer(
        buyer,
        request,
        acme_row,
        {line_id: 300},
        extra_costs=[{"kind": "shipping", "amount": 1500}],
    )
    compared = await _offer(buyer, request, bolt_row, {line_id: 250})

    assert compared["lines"][0]["cheapest_supplier_id"] == bolt_row["id"]
    totals = {row["id"]: row["total"] for row in compared["suppliers"]}
    assert totals == {acme_row["id"]: 2700, bolt_row["id"]: 1000}
    assert compared["cheapest_complete_supplier_id"] == bolt_row["id"]

    awarded = await _award(buyer, request, {line_id: bolt_row["id"]})

    assert awarded.status_code == 200, awarded.text
    body = awarded.json()
    assert body["request"]["status"] == "awarded"
    assert body["warnings"] == []
    [order_ref] = body["orders"]
    assert order_ref["created"] is True
    order = (await buyer.get(f"{ORDERS}/{order_ref['order_id']}")).json()
    assert order["status"] == "draft"
    assert order["supplier_id"] == bolt
    [order_line] = order["items"]
    assert order_line["price"] == 250
    assert order_line["quantity"] == 4.0
    assert order_line["quote_request_number"] == request["request_number"]
    assert await _allocated(buyer, demand) == 4.0
    awarded_line = body["request"]["lines"][0]
    assert awarded_line["state"] == "awarded"
    assert awarded_line["order_id"] == order["id"]
    links = (await buyer.get(f"{RFQ}/open-links", params={"bought_demand_ids": [demand]})).json()
    assert links["bought_demands"] == {}


async def test_quote_request_award_carries_the_offer_extra_costs(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 2.0)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 2.0, demand, 2.0)], [acme.id])
    line_id = request["lines"][0]["id"]
    row = request["suppliers"][0]
    await _offer(
        buyer,
        request,
        row,
        {line_id: 1000},
        extra_costs=[
            {"kind": "shipping", "amount": 1500},
            {"kind": "setup", "amount": 4000, "line_id": line_id},
        ],
    )

    awarded = await _award(buyer, request, {line_id: row["id"]})

    order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    costs = [(c["kind"], c["amount"]) for c in order["extra_costs"]]
    assert costs == [("shipping", 1500), ("setup", 4000)]
    assert order["extra_costs"][1]["order_item_id"] == order["items"][0]["id"]
    assert order["net_total"] == 2000 + 1500 + 4000


async def test_quote_request_award_cuts_a_share_to_what_the_demand_still_needs(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 5.0)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 5.0, demand, 5.0)], [acme.id])
    line_id = request["lines"][0]["id"]
    row = request["suppliers"][0]
    order = await graph.order()
    ordered = await buyer.post(
        f"{ORDERS}/{order.id}/items",
        json={
            "order_id": order.id,
            "supplier_id": order.supplier_id,
            "project_id": (await graph.project()).id,
            "bought_item_id": (await graph.bought_item()).id,
            "quantity": 3.0,
            "unit": "pcs",
            "bought_demand_allocations": [{"demand_item_id": demand, "quantity": 3.0}],
        },
    )
    assert ordered.status_code == 201, ordered.text

    awarded = await _award(buyer, request, {line_id: row["id"]})

    assert awarded.status_code == 200, awarded.text
    [warning] = awarded.json()["warnings"]
    assert warning["kind"] == "share_capped"
    assert await _allocated(buyer, demand) == 5.0
    new_order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    assert new_order["items"][0]["quantity"] == 5.0


async def test_quote_request_award_adds_to_an_existing_draft_of_the_supplier(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 1.0)
    acme = await graph.supplier()
    draft = (await buyer.post(f"{ORDERS}/", json={"supplier_id": acme.id})).json()
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    line_id = request["lines"][0]["id"]
    row = request["suppliers"][0]

    awarded = await _award(
        buyer,
        request,
        {line_id: row["id"]},
        suppliers=[
            {
                "supplier_row_id": row["id"],
                "target_order_id": draft["id"],
                "extra_costs": [{"kind": "packaging", "amount": 300}],
            }
        ],
    )

    assert awarded.status_code == 200, awarded.text
    assert awarded.json()["orders"][0] == {
        "order_id": draft["id"],
        "order_number": draft["order_number"],
        "supplier_id": acme.id,
        "supplier_name": "Acme",
        "created": False,
        "line_ids": [line_id],
    }
    order = (await buyer.get(f"{ORDERS}/{draft['id']}")).json()
    assert len(order["items"]) == 1
    assert [c["kind"] for c in order["extra_costs"]] == ["packaging"]
    assert order["edit_version"] == draft["edit_version"] + 1


async def _order_with_lines(buyer: Any, graph: Graph, supplier_id: int, *, ordered: int) -> dict:
    """An order of the supplier with two virtual lines, the first `ordered`
    of them marked ordered."""
    order = (await buyer.post(f"{ORDERS}/", json={"supplier_id": supplier_id})).json()
    project_id = (await graph.project()).id
    lines = []
    for index in range(2):
        added = await buyer.post(
            f"{ORDERS}/{order['id']}/items",
            json={
                "order_id": order["id"],
                "supplier_id": supplier_id,
                "project_id": project_id,
                "virtual_name": f"Freight {index}",
                "quantity": 1,
                "unit": "pcs",
            },
        )
        assert added.status_code == 201, added.text
        lines.append(added.json()["id"])
    for line in lines[:ordered]:
        marked = await buyer.put(f"{ORDERS}/{order['id']}/items/{line}/mark-ordered")
        assert marked.status_code == 200, marked.text
    return dict((await buyer.get(f"{ORDERS}/{order['id']}")).json())


async def test_an_award_refuses_a_target_order_submitted_while_it_was_prepared(
    graph: Graph, buyer: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The award reads its target orders before its locks. One submitted in
    between is read again under the lock and refuses the award, instead of
    taking a pending line on an ordered order."""
    demand = await _open_demand(graph, 1.0)
    acme = await graph.supplier()
    target = await _order_with_lines(buyer, graph, acme.id, ordered=2)
    assert target["status"] == "ordered"
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    row = request["suppliers"][0]

    async def read_before_the_submit(self: Any, _request: Any, _inputs: Any) -> dict:
        order = await self._r.orders.get_by_id(target["id"])
        return {row["id"]: replace(order, status=OrderStatus.DRAFT)}

    monkeypatch.setattr(AwardQuoteRequest, "_target_orders", read_before_the_submit)

    awarded = await _award(
        buyer,
        request,
        {request["lines"][0]["id"]: row["id"]},
        suppliers=[{"supplier_row_id": row["id"], "target_order_id": target["id"]}],
    )

    assert awarded.status_code == 409, awarded.text
    assert awarded.json()["code"] == "ConcurrentModificationError"
    order = (await buyer.get(f"{ORDERS}/{target['id']}")).json()
    assert len(order["items"]) == 2


async def test_quote_request_award_adds_to_a_partially_ordered_order_of_the_supplier(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 1.0)
    acme = await graph.supplier()
    target = await _order_with_lines(buyer, graph, acme.id, ordered=1)
    assert target["status"] == "partially_ordered"
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    row = request["suppliers"][0]

    awarded = await _award(
        buyer,
        request,
        {request["lines"][0]["id"]: row["id"]},
        suppliers=[{"supplier_row_id": row["id"], "target_order_id": target["id"]}],
    )

    assert awarded.status_code == 200, awarded.text
    assert awarded.json()["orders"][0]["order_id"] == target["id"]
    order = (await buyer.get(f"{ORDERS}/{target['id']}")).json()
    assert len(order["items"]) == 3
    assert order["status"] == "partially_ordered"


async def test_quote_request_award_to_an_ordered_order_is_refused(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 1.0)
    acme = await graph.supplier()
    target = await _order_with_lines(buyer, graph, acme.id, ordered=2)
    assert target["status"] == "ordered"
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    row = request["suppliers"][0]

    refused = await _award(
        buyer,
        request,
        {request["lines"][0]["id"]: row["id"]},
        suppliers=[{"supplier_row_id": row["id"], "target_order_id": target["id"]}],
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "QuoteRequestInvalidError"
    assert len((await buyer.get(f"{ORDERS}/{target['id']}")).json()["items"]) == 2


async def test_quote_request_award_to_a_supplier_without_an_offer_is_refused(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 1.0)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    line_id = request["lines"][0]["id"]
    row = request["suppliers"][0]
    saved = await buyer.put(
        f"{RFQ}/{request['id']}/suppliers/{row['id']}/offer",
        json={"quotes": [{"line_id": line_id, "no_offer": True}]},
    )
    assert saved.status_code == 200, saved.text

    refused = await _award(buyer, request, {line_id: row["id"]})

    assert refused.status_code == 422
    assert await _allocated(buyer, demand) == 0.0


async def test_quote_request_award_with_an_older_edit_version_is_refused(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 1.0)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    edited = await buyer.put(
        f"{RFQ}/{request['id']}", json={"note": "Urgent", "expected_edit_version": 0}
    )
    assert edited.json()["edit_version"] == 1

    refused = await buyer.post(
        f"{RFQ}/{request['id']}/award",
        json={
            "awards": [
                {
                    "line_id": request["lines"][0]["id"],
                    "supplier_row_id": request["suppliers"][0]["id"],
                }
            ],
            "expected_edit_version": 0,
        },
    )

    assert refused.status_code == 409


async def test_quote_request_made_line_assigns_its_lot_position(graph: Graph, buyer: Any) -> None:
    position = await graph.internal_position()
    acme = await graph.supplier()
    request = await _request(
        buyer,
        graph,
        [{"lot_position_id": position.id, "quantity": 4.0, "unit": "pcs"}],
        [acme.id],
    )
    line = request["lines"][0]
    assert line["line_type"] == "MADE"
    assert line["lot_number"] == "L-1"
    row = request["suppliers"][0]
    await _offer(buyer, request, row, {line["id"]: 9000})
    links = (
        await buyer.get(f"{RFQ}/open-links", params={"lot_position_ids": [position.id]})
    ).json()
    assert list(links["lot_positions"]) == [str(position.id)]

    awarded = await _award(buyer, request, {line["id"]: row["id"]})

    assert awarded.status_code == 200, awarded.text
    order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    [order_line] = order["items"]
    assert order_line["line_type"] == "MADE"
    assert order_line["quantity"] == 4.0
    assert order_line["price"] == 9000
    assert order_line["quote_request_line_id"] == line["id"]


async def test_quote_request_lines_added_after_sending_were_not_asked(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 2.0)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    row = request["suppliers"][0]
    await buyer.post(f"{RFQ}/{request['id']}/suppliers/{row['id']}/sent")

    added = await buyer.post(
        f"{RFQ}/{request['id']}/lines",
        json={"lines": [await _bought_line(graph, 1.0, demand, 1.0)]},
    )

    assert added.status_code == 200, added.text
    new_line = added.json()["lines"][1]
    assert added.json()["suppliers"][0]["not_asked_line_ids"] == [new_line["id"]]
    resent = await buyer.post(f"{RFQ}/{request['id']}/suppliers/{row['id']}/sent")
    assert resent.json()["suppliers"][0]["not_asked_line_ids"] == []


async def test_quote_request_takes_an_archived_supplier(graph: Graph, buyer: Any) -> None:
    archived = await _second_supplier(graph, archived=True)
    request = await _request(buyer, graph, [], [])

    added = await buyer.post(f"{RFQ}/{request['id']}/suppliers", json={"supplier_ids": [archived]})

    assert added.status_code == 200, added.text
    assert added.json()["suppliers"][0]["supplier_archived"] is True


async def test_quote_request_cancel_and_close_follow_the_award(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 2.0)
    acme = await graph.supplier()
    lines = [
        await _bought_line(graph, 1.0, demand, 1.0),
        await _bought_line(graph, 1.0, demand, 1.0),
    ]
    request = await _request(buyer, graph, lines, [acme.id])
    first, second = request["lines"]
    row = request["suppliers"][0]
    await _award(buyer, request, {first["id"]: row["id"]})
    current = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert current["status"] == "draft"
    assert "cancel" not in current["actions"]

    refused = await buyer.post(
        f"{RFQ}/{request['id']}/cancel", params={"expected_edit_version": current["edit_version"]}
    )
    closed = await buyer.post(
        f"{RFQ}/{request['id']}/close", params={"expected_edit_version": current["edit_version"]}
    )

    assert refused.status_code == 409
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert [line["state"] for line in closed.json()["lines"]] == ["awarded", "dropped"]
    assert second["id"] == closed.json()["lines"][1]["id"]


async def test_quote_request_keeps_its_line_when_the_demand_is_deleted(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 2.0)
    request = await _request(buyer, graph, [await _bought_line(graph, 2.0, demand, 2.0)], [])
    repo = SqlAlchemyBoughtItemDemandItemRepository(graph.db)
    found = await repo.get_by_id(demand)
    assert found is not None

    await repo.delete(found)
    await graph.db.commit()

    current = (await buyer.get(f"{RFQ}/{request['id']}")).json()
    assert len(current["lines"]) == 1
    assert current["lines"][0]["demands"] == []


async def test_quote_request_needs_write_orders(graph: Graph, auth_client: Any) -> None:
    reader = await auth_client(username="reader", email="reader@example.com", permissions=[])

    refused = await reader.post(f"{RFQ}/", json={})

    assert refused.status_code == 403


async def test_quote_request_offer_documents_route_and_gate(
    graph: Graph, buyer: Any, auth_client: Any
) -> None:
    acme = await graph.supplier()
    request = await _request(buyer, graph, [], [acme.id])
    row_id = request["suppliers"][0]["id"]
    reader = await auth_client(username="reader2", email="reader2@example.com", permissions=[])
    files = f"{API_WEB}/quote-request-suppliers/{row_id}/files"

    listed = await reader.get(files)
    unknown = await buyer.get(f"{API_WEB}/quote-request-suppliers/999999/files")
    upload = await reader.post(
        files,
        files={"file": ("offer.pdf", b"%PDF-1.4", "application/pdf")},
        data={"category": "offer"},
    )
    removed = await buyer.delete(f"{RFQ}/{request['id']}/suppliers/{row_id}")

    assert listed.status_code == 200
    assert listed.json() == []
    assert unknown.status_code == 404
    assert upload.status_code == 403
    assert removed.status_code == 200, removed.text
    assert removed.json()["suppliers"] == []


async def _other_bought_item(graph: Graph) -> int:
    first = await graph.bought_item()
    saved = await SqlAlchemyBoughtItemRepository(graph.db).save(
        replace(
            first,
            id=0,
            article_name="Screw M6 A2",
            order_code_1="OC-2",
            part_number="B-2",
            gtin=None,
            ean=None,
            edp_part_id=None,
            pdm_file_id=None,
        )
    )
    await graph.db.commit()
    return saved.id


async def _bought_allocations(buyer: Any, demand_id: int) -> list[dict]:
    response = await buyer.get(f"{API_WEB}/bought-items-allocations/demand/{demand_id}")
    assert response.status_code == 200, response.text
    return list(response.json())


async def test_quote_request_award_puts_a_suppliers_alternative_on_the_order(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 3.0)
    alternative = await _other_bought_item(graph)
    acme = await graph.supplier()
    bolt = await _second_supplier(graph)
    request = await _request(
        buyer, graph, [await _bought_line(graph, 3.0, demand, 3.0)], [acme.id, bolt]
    )
    line_id = request["lines"][0]["id"]
    acme_row, bolt_row = request["suppliers"]
    await _offer(buyer, request, acme_row, {line_id: 400})
    quote = {
        "line_id": line_id,
        "unit_price": 350,
        "substitute_bought_item_id": alternative,
        "substitute_reason": "The requested screw is discontinued.",
    }
    response = await buyer.put(
        f"{RFQ}/{request['id']}/suppliers/{bolt_row['id']}/offer", json={"quotes": [quote]}
    )
    assert response.status_code == 200, response.text
    compared = response.json()

    [bolt_quote] = compared["suppliers"][1]["quotes"]
    assert bolt_quote["substitute_bought_item_id"] == alternative
    assert bolt_quote["substitute_item_name"] == "Screw M6 A2"
    # An alternative competes with the other offers for the line.
    assert compared["lines"][0]["cheapest_supplier_id"] == bolt_row["id"]

    awarded = await _award(buyer, request, {line_id: bolt_row["id"]})

    assert awarded.status_code == 200, awarded.text
    [order_ref] = awarded.json()["orders"]
    order = (await buyer.get(f"{ORDERS}/{order_ref['order_id']}")).json()
    assert order["items"][0]["bought_item_id"] == alternative
    [allocation] = await _bought_allocations(buyer, demand)
    assert allocation["substitute_item_id"] == alternative
    assert allocation["substitute_reason"] == "The requested screw is discontinued."


async def test_quote_request_alternative_must_be_of_the_lines_kind(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 1.0)
    alternative = await _other_bought_item(graph)
    source_item = await graph.source_item()
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    line_id = request["lines"][0]["id"]
    offer = f"{RFQ}/{request['id']}/suppliers/{request['suppliers'][0]['id']}/offer"

    without_reason = await buyer.put(
        offer,
        json={"quotes": [{"line_id": line_id, "substitute_bought_item_id": alternative}]},
    )
    other_kind = await buyer.put(
        offer,
        json={"quotes": [{"line_id": line_id, "substitute_source_item_id": source_item.id}]},
    )

    assert without_reason.status_code == 200, without_reason.text
    [quote] = without_reason.json()["suppliers"][0]["quotes"]
    assert (quote["substitute_bought_item_id"], quote["substitute_reason"]) == (alternative, None)
    assert other_kind.status_code == 422
    assert other_kind.json()["code"] == "QuoteRequestInvalidError"


async def test_quote_request_offer_can_be_recorded_again(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 2.0)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 2.0, demand, 2.0)], [acme.id])
    line_id = request["lines"][0]["id"]
    row = request["suppliers"][0]
    await _offer(
        buyer, request, row, {line_id: 300}, extra_costs=[{"kind": "shipping", "amount": 900}]
    )

    again = await _offer(buyer, request, row, {line_id: 280})

    [quote] = again["suppliers"][0]["quotes"]
    assert quote["unit_price"] == 280
    assert again["suppliers"][0]["extra_costs"] == []


async def test_quote_request_line_substitute_replaces_the_line_for_every_supplier(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 2.0)
    alternative = await _other_bought_item(graph)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 2.0, demand, 2.0)], [acme.id])
    old_id = request["lines"][0]["id"]
    row = request["suppliers"][0]
    await buyer.post(f"{RFQ}/{request['id']}/suppliers/{row['id']}/sent")

    response = await buyer.post(
        f"{RFQ}/{request['id']}/lines/{old_id}/substitute",
        json={"bought_item_id": alternative, "reason": "Stainless steel is required."},
    )

    assert response.status_code == 200, response.text
    old, new = response.json()["lines"]
    assert old["state"] == "dropped"
    assert old["substituted_by_line_id"] == new["id"]
    assert old["demands"] == []
    assert new["state"] == "open"
    assert new["bought_item_id"] == alternative
    assert new["substitute_reason"] == "Stainless steel is required."
    assert [(d["demand_item_id"], d["quantity"]) for d in new["demands"]] == [(demand, 2.0)]
    restore = await buyer.post(f"{RFQ}/{request['id']}/lines/{old_id}/restore")
    assert restore.status_code == 422

    await _offer(buyer, request, row, {new["id"]: 120})
    awarded = await _award(buyer, request, {new["id"]: row["id"]})

    assert awarded.status_code == 200, awarded.text
    [allocation] = await _bought_allocations(buyer, demand)
    assert allocation["substitute_item_id"] == alternative
    assert allocation["substitute_reason"] == "Stainless steel is required."


async def test_quote_request_removing_a_substitute_line_asks_for_the_old_one_again(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 2.0)
    alternative = await _other_bought_item(graph)
    request = await _request(buyer, graph, [await _bought_line(graph, 2.0, demand, 2.0)], [])
    old_id = request["lines"][0]["id"]
    substituted = await buyer.post(
        f"{RFQ}/{request['id']}/lines/{old_id}/substitute",
        json={"bought_item_id": alternative, "reason": "Stainless steel is required."},
    )
    new_id = substituted.json()["lines"][1]["id"]

    response = await buyer.delete(f"{RFQ}/{request['id']}/lines/{new_id}")

    assert response.status_code == 200, response.text
    [line] = response.json()["lines"]
    assert line["id"] == old_id
    assert line["state"] == "open"
    assert line["substituted_by_line_id"] is None
    assert [(d["demand_item_id"], d["quantity"]) for d in line["demands"]] == [(demand, 2.0)]


async def test_quote_request_made_line_takes_no_substitute(graph: Graph, buyer: Any) -> None:
    position = await graph.internal_position()
    alternative = await _other_bought_item(graph)
    made = {"lot_position_id": position.id, "quantity": 1.0, "unit": "pcs"}
    request = await _request(buyer, graph, [made], [])

    response = await buyer.post(
        f"{RFQ}/{request['id']}/lines/{request['lines'][0]['id']}/substitute",
        json={"bought_item_id": alternative, "reason": "Cheaper."},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "QuoteRequestInvalidError"


async def test_quote_request_offer_documents_list_for_a_supplier_with_an_offer(
    graph: Graph, buyer: Any
) -> None:
    demand = await _open_demand(graph, 1.0)
    alternative = await _other_bought_item(graph)
    acme = await graph.supplier()
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [acme.id])
    row = request["suppliers"][0]
    quote = {"line_id": request["lines"][0]["id"], "substitute_bought_item_id": alternative}
    await buyer.put(f"{RFQ}/{request['id']}/suppliers/{row['id']}/offer", json={"quotes": [quote]})

    listed = await buyer.get(f"{API_WEB}/quote-request-suppliers/{row['id']}/files")

    assert listed.status_code == 200, listed.text
    assert listed.json() == []


async def test_awarded_order_names_its_quote_requests(graph: Graph, buyer: Any) -> None:
    acme = await graph.supplier()
    first_demand = await _open_demand(graph, 1.0)
    second_demand = await _open_demand(graph, 1.0)
    first = await _request(
        buyer, graph, [await _bought_line(graph, 1.0, first_demand, 1.0)], [acme.id]
    )
    second = await _request(
        buyer, graph, [await _bought_line(graph, 1.0, second_demand, 1.0)], [acme.id]
    )
    awarded = await _award(buyer, first, {first["lines"][0]["id"]: first["suppliers"][0]["id"]})
    order_id = awarded.json()["orders"][0]["order_id"]
    # The second award adds its line to the same draft order.
    await _award(
        buyer,
        second,
        {second["lines"][0]["id"]: second["suppliers"][0]["id"]},
        suppliers=[{"supplier_row_id": second["suppliers"][0]["id"], "target_order_id": order_id}],
    )

    order = (await buyer.get(f"{ORDERS}/{order_id}")).json()
    listed = (await buyer.get(f"{ORDERS}/", params={"ids": [order_id]})).json()["items"]

    expected = [
        {"id": first["id"], "request_number": first["request_number"]},
        {"id": second["id"], "request_number": second["request_number"]},
    ]
    assert order["quote_requests"] == expected
    assert listed[0]["quote_requests"] == expected
    assert order["note"] is None
    assert {line["quote_request_number"] for line in order["items"]} == {
        first["request_number"],
        second["request_number"],
    }


async def test_quote_request_award_of_a_source_share_and_a_made_line_on_a_planned_lot(
    graph: Graph, buyer: Any
) -> None:
    """The MADE line's lot carries a made demand, which sorts before the
    source demand the other line shares in the lock order; the award locks
    both up front, so placing the MADE line locks nothing late."""
    await graph.made_allocation()
    position = await graph.internal_position()
    demand = await graph.source_demand()
    acme = await graph.supplier()
    made = {"lot_position_id": position.id, "quantity": 4.0, "unit": "pcs"}
    source = {
        "source_item_id": (await graph.source_item()).id,
        "project_id": (await graph.project()).id,
        "quantity": 3.0,
        "unit": "pcs",
        "demands": [{"family": "source", "demand_item_id": demand.id, "quantity": 3.0}],
    }
    request = await _request(buyer, graph, [made, source], [acme.id])
    row = request["suppliers"][0]
    lines = [line["id"] for line in request["lines"]]
    await _offer(buyer, request, row, dict.fromkeys(lines, 9000))

    awarded = await _award(buyer, request, dict.fromkeys(lines, row["id"]))

    assert awarded.status_code == 200, awarded.text
    order = (await buyer.get(f"{ORDERS}/{awarded.json()['orders'][0]['order_id']}")).json()
    assert sorted(item["line_type"] for item in order["items"]) == ["MADE", "SOURCE"]


async def test_quote_request_changelog_is_readable(graph: Graph, auth_client: Any) -> None:
    buyer = await auth_client(username="buyer", email="buyer@example.com", permissions=BUYER)
    demand = await _open_demand(graph, 1.0)
    request = await _request(buyer, graph, [await _bought_line(graph, 1.0, demand, 1.0)], [])
    canceled = await buyer.post(
        f"{RFQ}/{request['id']}/cancel", params={"expected_edit_version": request["edit_version"]}
    )
    assert canceled.status_code == 200, canceled.text
    reader = await auth_client(username="reader", email="reader@example.com", permissions=[])

    changelog = await reader.get(f"{RFQ}/{request['id']}/changelog")
    missing = await reader.get(f"{RFQ}/999999/changelog")

    assert changelog.status_code == 200, changelog.text
    lines = changelog.json()
    assert lines and all(isinstance(line, str) for line in lines)
    assert any("cancel" in line.lower() for line in lines)
    assert missing.status_code == 404
    assert missing.json()["code"] == "QuoteRequestNotFoundError"
