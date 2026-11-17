"""
The public_id resolve endpoint over real HTTP: create rows through their
normal create endpoints, read the public_id off the response, and confirm
GET /api/v1/web/resolve/{public_id} routes back to the right resource + id.
"""

import uuid

import pytest

from src.modules.platform.domain.value_objects.permission import Permission

WRITE = [Permission.WRITE_PROJECTS]


@pytest.fixture
async def writer(auth_client):
    return await auth_client(permissions=WRITE)


async def _customer(client, name="ACME"):
    r = await client.post("/api/v1/web/customers/", json={"name": name, "level": "A"})
    assert r.status_code == 201, r.text
    return r.json()


async def _product(client, number="P-001"):
    r = await client.post("/api/v1/web/products/", json={"product_number": number})
    assert r.status_code == 201, r.text
    return r.json()


async def test_resolves_a_customer(writer):
    customer = await _customer(writer)

    response = await writer.get(f"/api/v1/web/resolve/{customer['public_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == "customers"
    assert body["id"] == customer["id"]
    assert body["public_id"] == customer["public_id"]


async def test_resolves_a_product_distinctly_from_a_customer(writer):
    customer = await _customer(writer)
    product = await _product(writer)

    customer_resolved = (await writer.get(f"/api/v1/web/resolve/{customer['public_id']}")).json()
    product_resolved = (await writer.get(f"/api/v1/web/resolve/{product['public_id']}")).json()

    assert customer_resolved == {
        "resource": "customers",
        "id": customer["id"],
        "public_id": customer["public_id"],
    }
    assert product_resolved == {
        "resource": "products",
        "id": product["id"],
        "public_id": product["public_id"],
    }


async def test_unknown_public_id_returns_404(writer):
    response = await writer.get(f"/api/v1/web/resolve/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_malformed_public_id_returns_422(writer):
    response = await writer.get("/api/v1/web/resolve/not-a-uuid")

    assert response.status_code == 422


async def test_requires_authentication(client):
    response = await client.get(f"/api/v1/web/resolve/{uuid.uuid4()}")

    assert response.status_code == 401
