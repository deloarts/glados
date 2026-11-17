"""
The edit versions an edit or an irreversible action sends, read the way the
frontend reads them: from the order, line, lot or production order as the
API returns it now. A test reads the version right before the request, as a
user acts on the row they see.
"""

import httpx

_WEB = "/api/v1/web"


async def _read(client: httpx.AsyncClient, path: str, headers: dict[str, str] | None) -> dict:
    url = path if path.startswith("/api/") else f"{_WEB}{path}"
    response = await client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    body: dict = response.json()
    return body


async def order_version(
    client: httpx.AsyncClient, order_id: int, headers: dict[str, str] | None = None
) -> int:
    return int((await _read(client, f"/orders/{order_id}", headers))["edit_version"])


async def line_version(
    client: httpx.AsyncClient,
    order_id: int,
    line_id: int,
    headers: dict[str, str] | None = None,
) -> int:
    items = (await _read(client, f"/orders/{order_id}", headers))["items"]
    return int(next(item for item in items if item["id"] == line_id)["edit_version"])


async def lot_version(
    client: httpx.AsyncClient, lot_id: int, headers: dict[str, str] | None = None
) -> int:
    return int((await _read(client, f"/production-lots/{lot_id}", headers))["edit_version"])


async def production_order_version(
    client: httpx.AsyncClient, production_order_id: int, headers: dict[str, str] | None = None
) -> int:
    path = f"/production-orders/{production_order_id}"
    return int((await _read(client, path, headers))["edit_version"])


async def row_version(
    client: httpx.AsyncClient, path: str, headers: dict[str, str] | None = None
) -> int:
    """The edit version of the row the web API returns at `path`, such as
    "/suppliers/3", with or without the web API prefix."""
    return int((await _read(client, path, headers))["edit_version"])
