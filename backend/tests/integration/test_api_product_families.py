"""
Product families end to end: the master data routes (managed with the
article group permissions, live-name uniqueness, archive and restore) and
the bought item's product_family_id (set on create, changed and cleared on
update, filtered on, refused for an unknown or archived family).
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version
from tests.integration.repository_reads._graph import Graph

FAMILIES = f"{API_WEB}/product-families"
ITEMS = f"{API_WEB}/bought-items"


@pytest.fixture
async def buyer(auth_client) -> Any:
    return await auth_client(
        username="buyer",
        email="buyer@example.com",
        permissions=[
            Permission.WRITE_ARTICLE_GROUPS,
            Permission.WRITE_BOUGHT_ITEMS,
        ],
    )


@pytest.fixture
async def supplier_id(db, create_user) -> int:
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="other", email="other@example.com")
    supplier = await Graph(db, user, other).supplier()
    await db.commit()
    return supplier.id


async def _family(client: Any, name: str) -> int:
    response = await client.post(f"{FAMILIES}/", json={"name": name})
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _item(client: Any, supplier_id: int, **extra: Any) -> dict[str, Any]:
    response = await client.post(
        f"{ITEMS}/",
        json={
            "order_code_1": f"OC-{len(extra)}-{extra.get('product_family_id')}",
            "article_name": "Cylinder DSNU-20",
            "manufacturer_id": supplier_id,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_product_families_crud_and_live_name_uniqueness(buyer) -> None:
    family_id = await _family(buyer, "Cylinders")

    assert (await buyer.post(f"{FAMILIES}/", json={"name": "Cylinders"})).status_code == 409
    renamed = await buyer.put(
        f"{FAMILIES}/{family_id}", json={"name": "Pneumatic cylinders", "label_color": "#112233"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["label_color"] == "#112233"
    archived = await buyer.post(f"{FAMILIES}/{family_id}/archive")
    assert archived.json()["archived"] is True
    listed = await buyer.get(f"{FAMILIES}/")
    assert listed.json()["total"] == 0
    # An archived family frees its name for a new live one.
    await _family(buyer, "Pneumatic cylinders")
    assert (await buyer.post(f"{FAMILIES}/{family_id}/restore")).status_code == 409


async def test_product_families_need_the_article_group_permissions(auth_client) -> None:
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")

    assert (await reader.post(f"{FAMILIES}/", json={"name": "Valves"})).status_code == 403


async def test_product_family_is_set_changed_and_cleared_on_a_bought_item(
    buyer, supplier_id: int
) -> None:
    cylinders = await _family(buyer, "Cylinders")
    valves = await _family(buyer, "Valves")

    created = await _item(buyer, supplier_id, product_family_id=cylinders)
    assert created["product_family_id"] == cylinders
    assert created["product_family"]["name"] == "Cylinders"

    body = {
        "order_code_1": created["order_code_1"],
        "article_name": created["article_name"],
        "manufacturer_id": supplier_id,
        "status": created["status"],
        "product_family_id": valves,
    }
    changed = await buyer.put(
        f"{ITEMS}/{created['id']}",
        json={
            **body,
            "expected_edit_version": await row_version(buyer, f"{ITEMS}/{created['id']}"),
        },
    )
    assert changed.status_code == 200, changed.text
    reread = (await buyer.get(f"{ITEMS}/{created['id']}")).json()
    assert reread["product_family"]["name"] == "Valves"
    changelog = (await buyer.get(f"{ITEMS}/{created['id']}/changelog")).json()
    assert any("product_family_id" in line for line in changelog)

    cleared = await buyer.put(
        f"{ITEMS}/{created['id']}",
        json={
            "expected_edit_version": await row_version(buyer, f"{ITEMS}/{created['id']}"),
            **body,
            "product_family_id": None,
        },
    )
    assert cleared.json()["product_family"] is None


async def test_bought_items_filter_by_product_family(buyer, supplier_id: int) -> None:
    cylinders = await _family(buyer, "Cylinders")
    await _item(buyer, supplier_id, product_family_id=cylinders)
    await _item(buyer, supplier_id)

    response = await buyer.get(f"{ITEMS}/", params={"product_family_id": cylinders})

    assert response.status_code == 200, response.text
    assert [i["product_family_id"] for i in response.json()["items"]] == [cylinders]


async def test_bought_item_refuses_an_unknown_or_archived_product_family(
    buyer, supplier_id: int
) -> None:
    archived = await _family(buyer, "Old")
    await buyer.post(f"{FAMILIES}/{archived}/archive")
    base = {"order_code_1": "OC-X", "article_name": "X", "manufacturer_id": supplier_id}

    unknown = await buyer.post(f"{ITEMS}/", json={**base, "product_family_id": 999})
    gone = await buyer.post(f"{ITEMS}/", json={**base, "product_family_id": archived})

    assert unknown.status_code == 404
    assert unknown.json()["code"] == "ProductFamilyNotFoundError"
    assert gone.status_code == 404
