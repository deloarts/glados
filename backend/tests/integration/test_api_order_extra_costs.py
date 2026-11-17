"""
Extra costs of an order over HTTP: a save replaces the whole list and moves
the order's edit version, the totals count the priced live lines plus the
costs with a discount subtracted, a cost may name one of the order's lines
and falls back to the whole order when that line is removed, a cost of kind
"other" needs a label, an older edit version answers 409, and a canceled
order takes no change.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._edit_versions import line_version
from tests.integration._edit_versions import order_version
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    await seed_supplier(db)


@pytest.fixture
async def client(db, auth_client) -> Any:
    client = await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-410")
    )
    await db.commit()
    client.project_id = project.id
    return client


async def _order_with_line(client: Any, *, price: int | None = 250) -> tuple[int, int]:
    order = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    order_id = int(order.json()["id"])
    added = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": client.project_id,
            "virtual_name": "Bracket",
            "quantity": 4,
            "unit": "pcs",
            "price": price,
        },
    )
    assert added.status_code == 201, added.text
    return order_id, int(added.json()["id"])


async def _set(client: Any, order_id: int, costs: list[dict[str, Any]]) -> Any:
    version = await order_version(client, order_id)
    return await client.put(
        f"{ORDERS}/{order_id}/extra-costs",
        json={"costs": costs, "expected_edit_version": version},
    )


async def test_order_extra_costs_are_saved_and_counted_in_the_totals(client) -> None:
    order_id, _ = await _order_with_line(client)

    saved = await _set(
        client,
        order_id,
        [
            {"kind": "shipping", "amount": 1500},
            {"kind": "discount", "amount": 300},
        ],
    )

    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert [(c["kind"], c["amount"], c["position"]) for c in body["extra_costs"]] == [
        ("shipping", 1500, 1),
        ("discount", 300, 2),
    ]
    assert body["lines_total"] == 1000
    assert body["extra_costs_total"] == 1200
    assert body["net_total"] == 2200
    assert body["edit_version"] == 1
    read = (await client.get(f"{ORDERS}/{order_id}")).json()
    assert read["net_total"] == 2200


async def test_order_extra_costs_replace_the_previous_list(client) -> None:
    order_id, _ = await _order_with_line(client)
    await _set(client, order_id, [{"kind": "shipping", "amount": 1500}])

    replaced = await _set(client, order_id, [{"kind": "packaging", "amount": 400}])

    assert replaced.status_code == 200, replaced.text
    assert [c["kind"] for c in replaced.json()["extra_costs"]] == ["packaging"]
    cleared = await _set(client, order_id, [])
    assert cleared.json()["extra_costs"] == []
    assert cleared.json()["net_total"] == 1000


async def test_order_without_prices_or_costs_has_no_totals(client) -> None:
    order_id, _ = await _order_with_line(client, price=None)

    read = (await client.get(f"{ORDERS}/{order_id}")).json()

    assert read["lines_total"] is None
    assert read["extra_costs_total"] == 0
    assert read["net_total"] is None


async def test_order_extra_cost_of_a_removed_line_falls_back_to_the_order(client) -> None:
    order_id, line_id = await _order_with_line(client)
    saved = await _set(
        client, order_id, [{"kind": "setup", "amount": 5000, "order_item_id": line_id}]
    )
    assert saved.json()["extra_costs"][0]["order_item_id"] == line_id

    removed = await client.delete(
        f"{ORDERS}/{order_id}/items/{line_id}",
        params={"expected_edit_version": await line_version(client, order_id, line_id)},
    )

    assert removed.status_code in (200, 204), removed.text
    read = (await client.get(f"{ORDERS}/{order_id}")).json()
    assert read["extra_costs"][0]["order_item_id"] is None


async def test_order_extra_cost_naming_another_orders_line_is_refused(client) -> None:
    order_id, _ = await _order_with_line(client)
    _, other_line = await _order_with_line(client)

    refused = await _set(
        client, order_id, [{"kind": "setup", "amount": 5000, "order_item_id": other_line}]
    )

    assert refused.status_code == 422
    assert refused.json()["code"] == "ExtraCostInvalidError"


async def test_order_extra_cost_of_kind_other_needs_a_label(client) -> None:
    order_id, _ = await _order_with_line(client)

    refused = await _set(client, order_id, [{"kind": "other", "amount": 100, "label": "  "}])
    accepted = await _set(
        client, order_id, [{"kind": "other", "amount": 100, "label": "Pallet deposit"}]
    )

    assert refused.status_code == 422
    assert refused.json()["code"] == "ExtraCostInvalidError"
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["extra_costs"][0]["label"] == "Pallet deposit"


async def test_order_extra_costs_with_an_older_version_are_refused(client) -> None:
    order_id, _ = await _order_with_line(client)
    await _set(client, order_id, [{"kind": "shipping", "amount": 1500}])

    stale = await client.put(
        f"{ORDERS}/{order_id}/extra-costs",
        json={"costs": [{"kind": "shipping", "amount": 900}], "expected_edit_version": 0},
    )

    assert stale.status_code == 409
    read = (await client.get(f"{ORDERS}/{order_id}")).json()
    assert read["extra_costs"][0]["amount"] == 1500


async def test_order_extra_costs_need_the_edit_version(client) -> None:
    order_id, _ = await _order_with_line(client)

    refused = await client.put(f"{ORDERS}/{order_id}/extra-costs", json={"costs": []})

    assert refused.status_code == 422


async def test_canceled_order_takes_no_extra_costs(client) -> None:
    order_id, _ = await _order_with_line(client)
    version = await order_version(client, order_id)
    canceled = await client.put(
        f"{ORDERS}/{order_id}/cancel", params={"expected_edit_version": version}
    )
    assert canceled.status_code == 200, canceled.text

    refused = await _set(client, order_id, [{"kind": "shipping", "amount": 1500}])

    assert refused.status_code == 409
    assert refused.json()["code"] == "OrderCanceledError"


async def test_order_extra_costs_count_in_the_project_cost_summary(db, client) -> None:
    other = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-411")
    )
    await db.commit()
    order_id, line_id = await _order_with_line(client)  # 4 x 250 for P-410
    other_line = await client.post(
        f"{ORDERS}/{order_id}/items",
        json={
            "order_id": order_id,
            "supplier_id": 1,
            "project_id": other.id,
            "virtual_name": "Plate",
            "quantity": 1,
            "unit": "pcs",
            "price": 3000,
        },
    )
    assert other_line.status_code == 201, other_line.text
    await _set(
        client,
        order_id,
        [
            {"kind": "shipping", "amount": 800},
            {"kind": "setup", "amount": 500, "order_item_id": line_id},
        ],
    )

    summary = (await client.get(f"{API_WEB}/projects/{client.project_id}/summary")).json()

    # The line of P-410 carries 1000 of the order's 4000, so a quarter of the
    # shipping falls on it, beside its own setup cost.
    assert summary["total_ordered_cost"] == 1000 + 200 + 500
