"""
The routes that take an Idempotency-Key, over HTTP: a retry with the same
key and request is answered from the first request without booking again,
the same key with another request answers 422, a request without a key
books every time, and the key's record of what a request wrote commits with
the work, so a request that fails to record it books nothing.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import select

from src.bootstrap.main import app
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import (
    get_schedule_recompute_generation_counter,
)
from src.modules.platform.adapters.outbound.persistence.repositories.idempotency_key_repository import (
    SqlAlchemyIdempotencyKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._suppliers import seed_supplier

ORDERS = f"{API_WEB}/orders"
DELIVER = f"{API_WEB}/bought-items-allocations/order-item"


@pytest.fixture(autouse=True)
async def _supplier(db) -> None:
    """Supplier #1, which the orders and lines here name."""
    await seed_supplier(db)


@pytest.fixture
async def client(auth_client) -> Any:
    return await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
        ]
    )


@pytest.fixture
async def order_id(db, client) -> int:
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=1, project_number="P-320")
    )
    await db.commit()
    order = await client.post(f"{ORDERS}/", json={"supplier_id": 1})
    assert order.status_code == 201, order.text
    order_id = int(order.json()["id"])
    client.project_id = project.id
    return order_id


def _line_body(order_id: int, project_id: int, quantity: int = 10) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "supplier_id": 1,
        "project_id": project_id,
        "virtual_name": "Bracket",
        "quantity": quantity,
        "unit": "pcs",
    }


async def _ordered_line(client: Any, order_id: int) -> int:
    added = await client.post(
        f"{ORDERS}/{order_id}/items", json=_line_body(order_id, client.project_id)
    )
    assert added.status_code == 201, added.text
    line_id = int(added.json()["id"])
    marked = await client.put(f"{ORDERS}/{order_id}/items/{line_id}/mark-ordered")
    assert marked.status_code == 200, marked.text
    return line_id


async def _items(client: Any, order_id: int) -> list[dict[str, Any]]:
    return list((await client.get(f"{ORDERS}/{order_id}")).json()["items"])


async def test_a_retried_delivery_is_booked_once(client, order_id: int) -> None:
    line_id = await _ordered_line(client, order_id)
    headers = {"Idempotency-Key": "deliver-1"}

    first = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 4}, headers=headers
    )
    retry = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 4}, headers=headers
    )

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert retry.json()["quantity_delivered"] == 4
    [item] = await _items(client, order_id)
    assert item["quantity_delivered"] == 4
    assert len(item["delivery_records"]) == 1


async def test_the_same_key_with_another_request_is_refused(client, order_id: int) -> None:
    line_id = await _ordered_line(client, order_id)
    headers = {"Idempotency-Key": "deliver-2"}
    await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 4}, headers=headers)

    reused = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 3}, headers=headers
    )

    assert reused.status_code == 422, reused.text
    assert reused.json()["code"] == "IdempotencyKeyReusedError"
    [item] = await _items(client, order_id)
    assert item["quantity_delivered"] == 4


async def test_a_failed_request_frees_its_key(client, order_id: int) -> None:
    line_id = await _ordered_line(client, order_id)
    headers = {"Idempotency-Key": "deliver-3"}

    refused = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 99}, headers=headers
    )
    assert refused.status_code == 422, refused.text
    booked = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 99}, headers=headers
    )

    # The key is free again, so the same request is checked anew, not replayed.
    assert booked.status_code == 422, booked.text
    assert booked.json()["code"] != "IdempotencyKeyReusedError"


async def test_requests_without_a_key_book_every_time(client, order_id: int) -> None:
    line_id = await _ordered_line(client, order_id)

    for _ in range(2):
        booked = await client.put(f"{DELIVER}/{line_id}/deliver", params={"quantity": 2})
        assert booked.status_code == 200, booked.text

    [item] = await _items(client, order_id)
    assert item["quantity_delivered"] == 4


async def test_a_retried_deliver_all_replays_what_it_booked(client, order_id: int) -> None:
    delivered_id = await _ordered_line(client, order_id)
    pending = await client.post(
        f"{ORDERS}/{order_id}/items", json=_line_body(order_id, client.project_id)
    )
    pending_id = int(pending.json()["id"])
    headers = {"Idempotency-Key": "deliver-all-1"}

    first = await client.put(f"{ORDERS}/{order_id}/deliver-all-items", headers=headers)
    retry = await client.put(f"{ORDERS}/{order_id}/deliver-all-items", headers=headers)

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert [i["id"] for i in retry.json()["delivered"]] == [delivered_id]
    assert retry.json()["skipped"] == first.json()["skipped"]
    assert [s["order_item_id"] for s in retry.json()["skipped"]] == [pending_id]


async def test_a_retried_line_create_adds_one_line(client, order_id: int) -> None:
    headers = {"Idempotency-Key": "add-line-1"}
    body = _line_body(order_id, client.project_id)

    first = await client.post(f"{ORDERS}/{order_id}/items", json=body, headers=headers)
    retry = await client.post(f"{ORDERS}/{order_id}/items", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert len(await _items(client, order_id)) == 1


async def test_a_key_is_recorded_with_the_work_or_neither_commits(
    client, order_id: int, monkeypatch: Any
) -> None:
    line_id = await _ordered_line(client, order_id)
    headers = {"Idempotency-Key": "deliver-atomic"}
    repository = SqlAlchemyIdempotencyKeyRepository
    record = repository.mark_completed
    failures = iter([True])

    async def fail_once(self: Any, *args: Any, **kwargs: Any) -> Any:
        if next(failures, False):
            raise RuntimeError("the record of the key failed")
        return await record(self, *args, **kwargs)

    monkeypatch.setattr(repository, "mark_completed", fail_once)

    failed = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 4}, headers=headers
    )
    [unbooked] = await _items(client, order_id)
    retry = await client.put(
        f"{DELIVER}/{line_id}/deliver", params={"quantity": 4}, headers=headers
    )

    assert failed.status_code == 500, failed.text
    assert unbooked["quantity_delivered"] == 0
    assert retry.status_code == 200, retry.text
    [item] = await _items(client, order_id)
    assert item["quantity_delivered"] == 4
    assert len(item["delivery_records"]) == 1


async def test_a_keyed_write_requests_its_schedule_walk_after_its_commit(
    client, order_id: int
) -> None:
    """A walk that drew the generation before the delivery committed would
    cover it without seeing the delivery, so the request waits for the
    commit that ends the key's hold."""
    line_id = await _ordered_line(client, order_id)
    seen_at_increment: list[float] = []

    class _Counter:
        async def increment_generation(self) -> int:
            async with SessionLocal() as fresh:
                delivered = await fresh.scalar(
                    select(OrderItemOrmModel.quantity_delivered).filter_by(id=line_id)
                )
            seen_at_increment.append(float(delivered or 0))
            return len(seen_at_increment)

        async def mark_stale(self, at: datetime) -> None:
            pass

    app.dependency_overrides[get_schedule_recompute_generation_counter] = _Counter
    try:
        delivered = await client.put(
            f"{DELIVER}/{line_id}/deliver",
            params={"quantity": 4},
            headers={"Idempotency-Key": "deliver-walk"},
        )
    finally:
        app.dependency_overrides.pop(get_schedule_recompute_generation_counter, None)

    assert delivered.status_code == 200, delivered.text
    assert seen_at_increment == [4.0]
