"""The production order list's status and change filters as the queue board
sends them: several `statuses` in the query string, and `changed_from` as an
instant with its timezone."""

from collections.abc import Awaitable
from collections.abc import Callable

import httpx

URL = "/api/v1/web/production-orders/"

ClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


async def test_several_statuses_and_an_aware_changed_from_are_read_from_the_query(
    auth_client: ClientFactory,
) -> None:
    client = await auth_client(permissions=[])

    response = await client.get(
        URL,
        params=[
            ("statuses", "queued"),
            ("statuses", "paused"),
            ("changed_from", "2026-11-01T00:00:00Z"),
        ],
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


async def test_a_changed_from_without_a_timezone_is_refused(auth_client: ClientFactory) -> None:
    client = await auth_client(permissions=[])

    response = await client.get(URL, params={"changed_from": "2026-11-01T00:00:00"})

    assert response.status_code == 422


async def test_an_unknown_status_is_refused(auth_client: ClientFactory) -> None:
    client = await auth_client(permissions=[])

    response = await client.get(URL, params=[("statuses", "queued"), ("statuses", "lost")])

    assert response.status_code == 422
