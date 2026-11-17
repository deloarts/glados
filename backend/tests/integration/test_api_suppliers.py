"""
HTTP-level coverage of /api/v1/web/suppliers: a plain CRUD router, the
control case proving the integration harness generalises beyond the
complex production domain.
"""

import httpx
import pytest

from tests.integration._edit_versions import row_version


async def _create(client: httpx.AsyncClient, **overrides: object) -> dict:
    body = {"name": "Acme Fasteners", "level": "B"} | overrides
    resp = await client.post("/api/v1/web/suppliers/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_supplier_requires_write_permission(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=[])
    resp = await client.post("/api/v1/web/suppliers/", json={"name": "Acme"})
    assert resp.status_code == 403


async def test_create_supplier_rejects_missing_name(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=["write:suppliers"])
    resp = await client.post("/api/v1/web/suppliers/", json={})
    assert resp.status_code == 422


@pytest.mark.smoke
async def test_create_and_read_supplier(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=["write:suppliers"])
    created = await _create(client)
    resp = await client.get(f"/api/v1/web/suppliers/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Acme Fasteners"


async def test_read_missing_supplier_404(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=[])
    resp = await client.get("/api/v1/web/suppliers/999999")
    assert resp.status_code == 404


async def test_list_suppliers(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=["write:suppliers"])
    await _create(client)
    resp = await client.get("/api/v1/web/suppliers/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(s["name"] == "Acme Fasteners" for s in body["items"])


async def test_update_supplier_requires_write_permission(auth_client) -> None:
    owner: httpx.AsyncClient = await auth_client(
        username="owner", email="owner@example.com", permissions=[]
    )
    created = await _create(
        await auth_client(
            username="creator", email="creator@example.com", permissions=["write:suppliers"]
        )
    )
    resp = await owner.put(
        f"/api/v1/web/suppliers/{created['id']}",
        json={
            "expected_edit_version": await row_version(
                owner, f"/api/v1/web/suppliers/{created['id']}"
            ),
            "name": "Renamed",
            "level": "A",
        },
    )
    assert resp.status_code == 403


async def test_update_supplier(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=["write:suppliers"])
    created = await _create(client)
    resp = await client.put(
        f"/api/v1/web/suppliers/{created['id']}",
        json={
            "expected_edit_version": await row_version(
                client, f"/api/v1/web/suppliers/{created['id']}"
            ),
            "name": "Renamed",
            "level": "A",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_archive_supplier_requires_delete_permission(auth_client) -> None:
    creator: httpx.AsyncClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:suppliers"]
    )
    created = await _create(creator)
    resp = await creator.post(f"/api/v1/web/suppliers/{created['id']}/archive")
    assert resp.status_code == 403


@pytest.mark.smoke
async def test_archive_supplier(auth_client) -> None:
    creator: httpx.AsyncClient = await auth_client(
        username="creator", email="creator@example.com", permissions=["write:suppliers"]
    )
    created = await _create(creator)
    archiver: httpx.AsyncClient = await auth_client(
        username="archiver", email="archiver@example.com", permissions=["delete:suppliers"]
    )
    resp = await archiver.post(f"/api/v1/web/suppliers/{created['id']}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True


async def test_archive_supplier_is_idempotent(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(
        permissions=["write:suppliers", "delete:suppliers"]
    )
    created = await _create(client)
    first = await client.post(f"/api/v1/web/suppliers/{created['id']}/archive")
    second = await client.post(f"/api/v1/web/suppliers/{created['id']}/archive")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["archived"] is True


async def test_archived_supplier_hidden_from_default_list_but_resolves_by_id(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(
        permissions=["write:suppliers", "delete:suppliers"]
    )
    created = await _create(client, name="Archived Supplier Co")
    await client.post(f"/api/v1/web/suppliers/{created['id']}/archive")

    default_list = await client.get("/api/v1/web/suppliers/")
    assert default_list.status_code == 200
    assert all(s["id"] != created["id"] for s in default_list.json()["items"])

    included_list = await client.get("/api/v1/web/suppliers/", params={"include_archived": True})
    assert included_list.status_code == 200
    assert any(s["id"] == created["id"] for s in included_list.json()["items"])

    by_id = await client.get(f"/api/v1/web/suppliers/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["archived"] is True


async def test_restore_supplier(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(
        permissions=["write:suppliers", "delete:suppliers"]
    )
    created = await _create(client)
    await client.post(f"/api/v1/web/suppliers/{created['id']}/archive")

    resp = await client.post(f"/api/v1/web/suppliers/{created['id']}/restore")
    assert resp.status_code == 200
    assert resp.json()["archived"] is False

    default_list = await client.get("/api/v1/web/suppliers/")
    assert any(s["id"] == created["id"] for s in default_list.json()["items"])


async def test_restore_supplier_is_idempotent(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(
        permissions=["write:suppliers", "delete:suppliers"]
    )
    created = await _create(client)
    await client.post(f"/api/v1/web/suppliers/{created['id']}/archive")
    await client.post(f"/api/v1/web/suppliers/{created['id']}/restore")

    resp = await client.post(f"/api/v1/web/suppliers/{created['id']}/restore")
    assert resp.status_code == 200
    assert resp.json()["archived"] is False


async def test_restore_supplier_conflicts_on_vat_id_already_taken(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(
        permissions=["write:suppliers", "delete:suppliers"]
    )
    archived = await _create(client, name="Old Acme", vat_id="ATU12345678")
    await client.post(f"/api/v1/web/suppliers/{archived['id']}/archive")
    # A new, live supplier now legitimately claims the same VAT id, since
    # the partial unique index only guards live rows.
    await _create(client, name="New Acme", vat_id="ATU12345678")

    resp = await client.post(f"/api/v1/web/suppliers/{archived['id']}/restore")
    assert resp.status_code == 409
    assert resp.json()["code"] == "SupplierAlreadyExistsError"


async def test_supplier_created_and_changed_are_tz_aware_datetimes(auth_client) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=["write:suppliers"])
    created = await _create(client)
    for field in ("created", "changed"):
        value = created[field]
        assert "T" in value, f"{field}={value!r} is not a full datetime"
        assert value.endswith("+00:00") or value.endswith("Z"), (
            f"{field}={value!r} carries no UTC offset"
        )


async def test_supplier_created_from_date_only_expands_to_whole_day(auth_client) -> None:
    """The tenant's default timezone is the seeded Europe/Vienna, the one
    zone every calendar-date filter reads its days in. "Today" is computed
    in that zone, not UTC, so this holds regardless of what UTC instant the
    suite happens to run at."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    client: httpx.AsyncClient = await auth_client(permissions=["write:suppliers"])
    created = await _create(client)
    today = datetime.now(ZoneInfo("Europe/Vienna")).date().isoformat()

    resp = await client.get(
        "/api/v1/web/suppliers/", params={"created_from": today, "created_to": today}
    )
    assert resp.status_code == 200
    assert any(s["id"] == created["id"] for s in resp.json()["items"])

    resp_excluded = await client.get("/api/v1/web/suppliers/", params={"created_to": "2000-01-01"})
    assert resp_excluded.status_code == 200
    assert all(s["id"] != created["id"] for s in resp_excluded.json()["items"])
