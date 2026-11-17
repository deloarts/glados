"""
The manual status endpoints of bought, made and source item demands answer
one permission rule through HTTP. A user without write:demand_items and
another user get 403, the creator may set neither of the two irreversible
intents, canceled and fulfilled, and a manager may. A status the allocations
decide, such as ordered, cannot be set by hand and gets 422 once the actor
passes the permission rule. Every refusal is read back to show that the
stored status did not move.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.conftest import auth_headers
from tests.integration.repository_reads._graph import Graph

ROUTES = {
    "bought": f"{API_WEB}/bought-items-demands",
    "made": f"{API_WEB}/made-items-demands",
    "source": f"{API_WEB}/source-item-demands",
}

SEEDERS: dict[str, Callable[[Graph], Awaitable[Any]]] = {
    "bought": Graph.bought_demand,
    "made": Graph.made_demand,
    "source": Graph.source_demand,
}


@pytest.mark.parametrize("family", ["bought", "made", "source"])
async def test_demand_status_endpoint_applies_the_shared_permission_rule(
    family: str, client: Any, db: Any, create_user: Any
) -> None:
    write = [Permission.WRITE_DEMAND_ITEMS]
    creator = await create_user(username="creator", email="creator@example.com", permissions=write)
    other = await create_user(username="other", email="other@example.com", permissions=write)
    reader = await create_user(username="reader", email="reader@example.com", permissions=[])
    manager = await create_user(
        username="manager",
        email="manager@example.com",
        permissions=[*write, Permission.MANAGE_DEMAND_ITEMS],
    )
    # The graph seeds every demand as created by its first user, without
    # allocations, so it is open.
    demand = await SEEDERS[family](Graph(db, creator, other))
    await db.commit()
    url = f"{ROUTES[family]}/{demand.id}"

    async def put_status(user: Any, target: str) -> Any:
        return await client.put(
            f"{url}/status", params={"new_status": target}, headers=await auth_headers(user)
        )

    async def stored_status() -> str:
        response = await client.get(url, headers=await auth_headers(reader))
        assert response.status_code == 200, response.text
        return str(response.json()["status"])

    refusals = [
        (reader, "ordered", "InsufficientPermissionsError"),
        (reader, "fulfilled", "InsufficientPermissionsError"),
        (other, "ordered", "DemandItemOfAnotherUserError"),
        (other, "canceled", "DemandItemOfAnotherUserError"),
        (creator, "fulfilled", "InsufficientPermissionsError"),
        (creator, "canceled", "InsufficientPermissionsError"),
    ]
    for user, target, code in refusals:
        response = await put_status(user, target)
        assert response.status_code == 403, (user.username, target, response.text)
        assert response.json()["code"] == code
        assert await stored_status() == "open"

    response = await put_status(creator, "ordered")
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "DemandItemInvalidStatusTransitionError"
    assert await stored_status() == "open"

    response = await put_status(manager, "fulfilled")
    assert response.status_code == 200, response.text
    assert await stored_status() == "fulfilled"
