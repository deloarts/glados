"""
The changer of the catalogue and master data records over HTTP: an update
by a second user records that user as `changed_by_id` next to the unchanged
creator, a reread returns the same changer, and the lists filter on it.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.adapters.outbound.persistence.models.print_template_model import (
    PrintTemplateOrmModel,
)
from src.shared_kernel.domain.services.clock import now_utc

_PERMISSIONS = [
    Permission.WRITE_ARTICLE_GROUPS,
    Permission.WRITE_SOURCE_ITEM_TYPES,
    Permission.WRITE_FABRICATION_METHODS,
    Permission.WRITE_INSPECTION_METHODS,
    Permission.WRITE_SUPPLIERS,
    Permission.WRITE_SOURCE_ITEMS,
    Permission.WRITE_BOUGHT_ITEMS,
    Permission.WRITE_PROJECTS,
    Permission.MANAGE_PROJECTS,
    Permission.WRITE_PRINTERS,
]

Client = httpx.AsyncClient


@pytest.fixture
async def writer(auth_client) -> Client:
    return await auth_client(permissions=_PERMISSIONS)


@pytest.fixture
async def editor(auth_client) -> Client:
    return await auth_client(
        permissions=_PERMISSIONS, username="editor", email="editor@example.com"
    )


async def _post(client: Client, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(f"{API_WEB}/{path}/", json=body)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _supplier(client: Client) -> int:
    return int((await _post(client, "suppliers", {"name": "Acme", "level": "B"}))["id"])


async def _source_item_type(client: Client) -> int:
    return int((await _post(client, "source-item-types", {"name": {"enGB": "Sheet"}}))["id"])


def _labeled(name: str) -> Callable[[Client], Awaitable[dict[str, Any]]]:
    async def _body(_client: Client) -> dict[str, Any]:
        return {"name": name}

    return _body


def _localized(name: str) -> Callable[[Client], Awaitable[dict[str, Any]]]:
    async def _body(_client: Client) -> dict[str, Any]:
        return {"name": {"enGB": name}}

    return _body


async def _supplier_body(_client: Client) -> dict[str, Any]:
    return {"name": "Changer Supplier", "level": "B"}


async def _source_item_body(client: Client) -> dict[str, Any]:
    return {"type_id": await _source_item_type(client), "material": "S235"}


async def _bought_item_body(client: Client) -> dict[str, Any]:
    return {
        "order_code_1": "OC-CHANGER",
        "article_name": "Cylinder",
        "manufacturer_id": await _supplier(client),
    }


async def _project_body(_client: Client) -> dict[str, Any]:
    return {"project_number": "P-CHANGER"}


# The records whose update request requires the status, which the update
# sends back unchanged.
_STATUS_ON_UPDATE = frozenset({"source-items", "bought-items"})

# The records whose name and description are language maps.
_LOCALIZED = frozenset(
    {"article-groups", "source-item-types", "fabrication-methods", "inspection-methods"}
)

# (path, body builder, the field the update changes, the update method)
_RECORDS = [
    ("article-groups", _localized("Fasteners"), "description", "put"),
    ("source-item-types", _localized("Rods"), "description", "put"),
    ("fabrication-methods", _localized("Milling"), "description", "put"),
    ("inspection-methods", _localized("Visual"), "description", "put"),
    ("product-families", _labeled("Valves"), "description", "put"),
    ("suppliers", _supplier_body, "email", "put"),
    ("source-items", _source_item_body, "note", "put"),
    ("bought-items", _bought_item_body, "note", "put"),
    ("projects", _project_body, "description", "put"),
]


@pytest.mark.parametrize(("path", "body_of", "field", "method"), _RECORDS, ids=lambda v: v)
async def test_an_update_records_the_changing_user(
    writer: Client, editor: Client, path: str, body_of: Any, field: str, method: str
) -> None:
    body = await body_of(writer)
    created = await _post(writer, path, body)
    assert created["changed_by_id"] in (None, created["creator_id"])

    status = {"status": created["status"]} if path in _STATUS_ON_UPDATE else {}
    # The rows that carry an edit version send the one they read.
    version = (
        {"expected_edit_version": created["edit_version"]} if "edit_version" in created else {}
    )
    edited: str | dict[str, str] = {"enGB": "Edited"} if path in _LOCALIZED else "Edited"
    response = await getattr(editor, method)(
        f"{API_WEB}/{path}/{created['id']}",
        json={**body, **status, **version, field: edited},
    )
    assert response.status_code == 200, response.text
    updated = response.json()

    assert updated["creator_id"] == created["creator_id"]
    assert updated["changed_by_id"] not in (None, created["creator_id"])
    assert updated["changed_by"]["id"] == updated["changed_by_id"]
    reread = (await writer.get(f"{API_WEB}/{path}/{created['id']}")).json()
    assert reread["changed_by_id"] == updated["changed_by_id"]

    listed = (
        await writer.get(f"{API_WEB}/{path}/", params={"changed_by_id": updated["changed_by_id"]})
    ).json()
    assert [row["id"] for row in listed["items"]] == [created["id"]]
    missed = (
        await writer.get(
            f"{API_WEB}/{path}/", params={"changed_by_id": updated["changed_by_id"] + 999}
        )
    ).json()
    assert missed["items"] == []


_PRINTER = {
    "name": "Label Printer 1",
    "kind": "zpl_label",
    "host": "10.0.0.50",
    "port": 9100,
    "transport": "raw",
}


async def test_a_printer_update_records_the_changing_user(writer: Client, editor: Client) -> None:
    created = await _post(writer, "printers", _PRINTER)

    response = await editor.patch(f"{API_WEB}/printers/{created['id']}", json={"note": "Edited"})
    assert response.status_code == 200, response.text
    updated = response.json()

    assert updated["creator_id"] == created["creator_id"]
    assert updated["changed_by_id"] not in (None, created["creator_id"])
    assert updated["changed_by_full_name"]
    listed = (
        await writer.get(f"{API_WEB}/printers/", params={"changed_by_id": updated["changed_by_id"]})
    ).json()
    assert [row["id"] for row in listed["items"]] == [created["id"]]


async def test_a_print_template_update_records_the_changing_user(db, editor: Client) -> None:
    db.add(PrintTemplateOrmModel(created=now_utc(), classifier="lot_label"))
    await db.commit()

    response = await editor.patch(f"{API_WEB}/print-templates/lot_label", json={"note": "Edited"})
    assert response.status_code == 200, response.text
    updated = response.json()

    assert updated["changed_by_id"] is not None
    assert updated["changed_by_full_name"]
    reread = (await editor.get(f"{API_WEB}/print-templates/lot_label")).json()
    assert reread["changed_by_id"] == updated["changed_by_id"]
