"""
A product's variants over HTTP: the list is saved as a whole, kept names
can swap places, a variant left out is archived and can come back, and
editing needs the rights to edit the product. Every write is read back
through a separate request, so a missing commit fails here.
"""

from typing import Any

import httpx
import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission


@pytest.fixture
async def manager(auth_client: Any) -> httpx.AsyncClient:
    c: httpx.AsyncClient = await auth_client(
        permissions=[Permission.WRITE_PROJECTS, Permission.MANAGE_PROJECTS]
    )
    return c


async def _product(client: httpx.AsyncClient) -> int:
    r = await client.post(f"{API_WEB}/products/", json={"product_number": "M26001"})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def _save(client: httpx.AsyncClient, product_id: int, variants: list[dict[str, Any]]) -> Any:
    return await client.put(
        f"{API_WEB}/products/{product_id}/variants", json={"variants": variants}
    )


async def _names(client: httpx.AsyncClient, product_id: int, archived: bool = False) -> list[str]:
    r = await client.get(
        f"{API_WEB}/products/{product_id}/variants", params={"include_archived": archived}
    )
    assert r.status_code == 200, r.text
    return [v["name"] for v in r.json()]


async def test_product_variants_save_swap_archive_and_restore(manager: httpx.AsyncClient) -> None:
    product_id = await _product(manager)
    r = await _save(manager, product_id, [{"name": "Clamp 60"}, {"name": "Clamp 80"}])
    assert r.status_code == 200, r.text
    first, second = r.json()
    assert await _names(manager, product_id) == ["Clamp 60", "Clamp 80"]

    r = await _save(
        manager,
        product_id,
        [{"id": first["id"], "name": "Clamp 80"}, {"id": second["id"], "name": "Clamp 60"}],
    )
    assert r.status_code == 200, r.text
    assert await _names(manager, product_id) == ["Clamp 80", "Clamp 60"]

    r = await _save(manager, product_id, [{"id": first["id"], "name": "Clamp 80"}])
    assert r.status_code == 200, r.text
    assert await _names(manager, product_id) == ["Clamp 80"]
    assert await _names(manager, product_id, archived=True) == ["Clamp 80", "Clamp 60"]

    r = await _save(
        manager,
        product_id,
        [{"id": first["id"], "name": "Clamp 80"}, {"id": second["id"], "name": "Clamp 60"}],
    )
    assert r.status_code == 200, r.text
    assert await _names(manager, product_id) == ["Clamp 80", "Clamp 60"]


async def test_product_variants_reject_duplicates(manager: httpx.AsyncClient) -> None:
    product_id = await _product(manager)
    r = await _save(manager, product_id, [{"name": "Clamp"}, {"name": "clamp"}])
    assert r.status_code == 422
    assert await _names(manager, product_id) == []


async def test_product_variants_edit_needs_product_rights(
    manager: httpx.AsyncClient, auth_client: Any
) -> None:
    product_id = await _product(manager)
    outsider = await auth_client(
        permissions=[Permission.WRITE_PROJECTS], username="outsider", email="outsider@example.com"
    )
    r = await _save(outsider, product_id, [{"name": "Clamp"}])
    assert r.status_code == 403
    assert (await outsider.get(f"{API_WEB}/products/{product_id}/variants")).status_code == 200
