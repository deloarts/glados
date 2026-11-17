"""
HTTP-level coverage of /api/v1/web/printers: the physical-device-
config admin surface for ZPL/IPP label and document printers. Reads are
open to any authenticated user; create, update, archive and restore
require write:printers (PrinterRules).

`test-print` and `status` both reach out over the network to the physical
printer (see printers.py's own docstrings: "Send a built-in self-test job"
/ "Query the printer for identity + status"), so neither is exercised
here. Everything else is pure DB CRUD and is covered.
"""

import pytest
from fastapi.testclient import TestClient


async def _create(client: TestClient, **overrides: object) -> dict:
    body = {
        "name": "Label Printer 1",
        "kind": "zpl_label",
        "host": "10.0.0.50",
        "port": 9100,
        "transport": "raw",
    } | overrides
    resp = await client.post("/api/v1/web/printers/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_printer_requires_write_permission(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.post(
        "/api/v1/web/printers/",
        json={
            "name": "Label Printer 1",
            "kind": "zpl_label",
            "host": "10.0.0.50",
            "port": 9100,
            "transport": "raw",
        },
    )
    assert resp.status_code == 403


async def test_create_printer_rejects_missing_host(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    resp = await client.post(
        "/api/v1/web/printers/",
        json={"name": "Label Printer 1", "kind": "zpl_label", "port": 9100, "transport": "raw"},
    )
    assert resp.status_code == 422


@pytest.mark.smoke
async def test_create_and_read_printer(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    created = await _create(client)
    resp = await client.get(f"/api/v1/web/printers/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Label Printer 1"


async def test_read_printer_needs_no_special_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:printers"]
    )
    created = await _create(creator)
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )
    resp = await reader.get(f"/api/v1/web/printers/{created['id']}")
    assert resp.status_code == 200


async def test_read_missing_printer_404(auth_client) -> None:
    client: TestClient = await auth_client(permissions=[])
    resp = await client.get("/api/v1/web/printers/999999")
    assert resp.status_code == 404


async def test_list_printers(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    await _create(client)
    resp = await client.get("/api/v1/web/printers/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(p["name"] == "Label Printer 1" for p in body["items"])


async def test_update_printer_requires_write_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:printers"]
    )
    created = await _create(creator)
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )
    resp = await reader.patch(f"/api/v1/web/printers/{created['id']}", json={"name": "Renamed"})
    assert resp.status_code == 403


async def test_update_printer(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    created = await _create(client)
    resp = await client.patch(f"/api/v1/web/printers/{created['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_archive_printer_requires_write_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:printers"]
    )
    created = await _create(creator)
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )
    resp = await reader.post(f"/api/v1/web/printers/{created['id']}/archive")
    assert resp.status_code == 403


async def test_archive_printer(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:printers"]
    )
    created = await _create(creator)
    archiver: TestClient = await auth_client(
        username="archiver", email="archiver@example.com", permissions=["write:printers"]
    )
    resp = await archiver.post(f"/api/v1/web/printers/{created['id']}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True


async def test_archiving_a_printer_twice_is_idempotent(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    created = await _create(client)

    first = await client.post(f"/api/v1/web/printers/{created['id']}/archive")
    second = await client.post(f"/api/v1/web/printers/{created['id']}/archive")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["archived"] is True


async def test_archived_printer_hidden_from_default_list_but_resolves_by_id(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    created = await _create(client, name="Archived Printer")

    await client.post(f"/api/v1/web/printers/{created['id']}/archive")

    default_list = await client.get("/api/v1/web/printers/")
    assert all(p["id"] != created["id"] for p in default_list.json()["items"])

    included_list = await client.get("/api/v1/web/printers/", params={"include_archived": True})
    assert any(p["id"] == created["id"] for p in included_list.json()["items"])

    by_id = await client.get(f"/api/v1/web/printers/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["archived"] is True


async def test_restore_printer(auth_client) -> None:
    client: TestClient = await auth_client(permissions=["write:printers"])
    created = await _create(client)
    await client.post(f"/api/v1/web/printers/{created['id']}/archive")

    resp = await client.post(f"/api/v1/web/printers/{created['id']}/restore")

    assert resp.status_code == 200
    assert resp.json()["archived"] is False


async def test_restoring_a_printer_twice_is_idempotent(auth_client) -> None:
    """Printer has no unique index scoped to `archived` (unlike supplier's
    VAT id), so restore idempotency here pins the plain "already live is
    not an error" path without any uniqueness-conflict interaction."""
    client: TestClient = await auth_client(permissions=["write:printers"])
    created = await _create(client)
    await client.post(f"/api/v1/web/printers/{created['id']}/archive")
    await client.post(f"/api/v1/web/printers/{created['id']}/restore")

    resp = await client.post(f"/api/v1/web/printers/{created['id']}/restore")

    assert resp.status_code == 200
    assert resp.json()["archived"] is False


async def test_restore_printer_requires_write_permission(auth_client) -> None:
    creator: TestClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:printers"]
    )
    created = await _create(creator)
    await creator.post(f"/api/v1/web/printers/{created['id']}/archive")
    reader: TestClient = await auth_client(
        username="reader", email="reader@example.com", permissions=[]
    )

    resp = await reader.post(f"/api/v1/web/printers/{created['id']}/restore")

    assert resp.status_code == 403
