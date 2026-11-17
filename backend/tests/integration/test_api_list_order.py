"""
Hand-ordered resource lists over HTTP: a list without an explicit sort comes
in its hand-kept order, new entries go last, a move shifts an entry one
place and survives a fresh request, a place drops it next to a neighbour,
and both need the right to edit.
"""

from typing import Any

import httpx
import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission


def _labeled(name: str) -> dict[str, Any]:
    return {"name": {"enGB": name}}


def _plain(name: str) -> dict[str, Any]:
    return {"name": name}


def _machine(name: str) -> dict[str, Any]:
    return {"internal_name": name, "vendor": "DMG", "model": "DMU 50"}


LISTS = [
    pytest.param("article-groups", Permission.WRITE_ARTICLE_GROUPS, _labeled, id="article-groups"),
    pytest.param(
        "source-item-types", Permission.WRITE_SOURCE_ITEM_TYPES, _labeled, id="source-item-types"
    ),
    pytest.param(
        "fabrication-methods", Permission.WRITE_FABRICATION_METHODS, _labeled, id="fabrication"
    ),
    pytest.param(
        "inspection-methods", Permission.WRITE_INSPECTION_METHODS, _labeled, id="inspection"
    ),
    pytest.param("product-families", Permission.WRITE_ARTICLE_GROUPS, _plain, id="families"),
    pytest.param("production-machines", Permission.WRITE_MACHINES, _machine, id="machines"),
]

# Machine pools are only ever dragged, so they have no move endpoint.
PLACE_LISTS = [
    *LISTS,
    pytest.param("production-machine-pools", Permission.WRITE_MACHINES, _plain, id="pools"),
]


async def _create(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> int:
    r = await client.post(f"{API_WEB}/{path}/", json=body)
    assert r.status_code in (200, 201), r.text
    return int(r.json()["id"])


async def _listed(client: httpx.AsyncClient, path: str, ids: list[int]) -> list[int]:
    r = await client.get(f"{API_WEB}/{path}/", params={"limit": 100})
    assert r.status_code == 200, r.text
    return [row["id"] for row in r.json()["items"] if row["id"] in ids]


@pytest.mark.parametrize(("path", "permission", "body"), LISTS)
async def test_list_order_move_shifts_an_entry_one_place(
    auth_client: Any, path: str, permission: str, body: Any
) -> None:
    writer = await auth_client(permissions=[permission])
    # Created in reverse alphabetical order, so a name sort would differ.
    ids = [await _create(writer, path, body(name)) for name in ("Zeta", "Kappa", "Alpha")]
    assert await _listed(writer, path, ids) == ids

    r = await writer.post(f"{API_WEB}/{path}/{ids[2]}/move", json={"direction": "up"})
    assert r.status_code == 204, r.text
    assert await _listed(writer, path, ids) == [ids[0], ids[2], ids[1]]

    r = await writer.post(f"{API_WEB}/{path}/{ids[0]}/move", json={"direction": "up"})
    assert r.status_code == 204, r.text
    assert await _listed(writer, path, ids) == [ids[0], ids[2], ids[1]]


@pytest.mark.parametrize(("path", "permission", "body"), LISTS)
async def test_list_order_move_needs_the_edit_right_and_a_known_entry(
    auth_client: Any, path: str, permission: str, body: Any
) -> None:
    writer = await auth_client(permissions=[permission])
    entry_id = await _create(writer, path, body("Alpha"))
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")

    r = await reader.post(f"{API_WEB}/{path}/{entry_id}/move", json={"direction": "down"})
    assert r.status_code == 403

    r = await writer.post(f"{API_WEB}/{path}/999999/move", json={"direction": "down"})
    assert r.status_code == 404


@pytest.mark.parametrize(("path", "permission", "body"), PLACE_LISTS)
async def test_list_order_place_drops_an_entry_next_to_a_neighbour(
    auth_client: Any, path: str, permission: str, body: Any
) -> None:
    writer = await auth_client(permissions=[permission])
    ids = [await _create(writer, path, body(name)) for name in ("A", "B", "C", "D")]
    assert await _listed(writer, path, ids) == ids

    r = await writer.post(f"{API_WEB}/{path}/{ids[0]}/place", json={"after_id": ids[2]})
    assert r.status_code == 204, r.text
    assert await _listed(writer, path, ids) == [ids[1], ids[2], ids[0], ids[3]]

    r = await writer.post(f"{API_WEB}/{path}/{ids[3]}/place", json={"before_id": ids[1]})
    assert r.status_code == 204, r.text
    assert await _listed(writer, path, ids) == [ids[3], ids[1], ids[2], ids[0]]

    both = await writer.post(
        f"{API_WEB}/{path}/{ids[0]}/place", json={"after_id": ids[1], "before_id": ids[2]}
    )
    assert both.status_code == 422
    unknown = await writer.post(f"{API_WEB}/{path}/{ids[0]}/place", json={"after_id": 999999})
    assert unknown.status_code == 404

    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    r = await reader.post(f"{API_WEB}/{path}/{ids[0]}/place", json={})
    assert r.status_code == 403
