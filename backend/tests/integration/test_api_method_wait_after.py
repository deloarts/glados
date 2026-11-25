"""
wait_after_minutes on fabrication and inspection methods through the web
API: the clock minutes the pieces wait after a step of the method before
the next step may start. Empty means no wait, and a negative value is
refused. The field is web only, so the frozen pat shape stays as it is.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission

FABRICATION = f"{API_WEB}/fabrication-methods"
INSPECTION = f"{API_WEB}/inspection-methods"


@pytest.fixture
async def client(auth_client) -> Any:
    return await auth_client(
        permissions=[Permission.WRITE_FABRICATION_METHODS, Permission.WRITE_INSPECTION_METHODS]
    )


@pytest.mark.parametrize("base", [FABRICATION, INSPECTION])
async def test_the_wait_round_trips(client, base: str) -> None:
    created = await client.post(f"{base}/", json={"name": {"enGB": "Curing"}})
    assert created.status_code == 201, created.text
    assert created.json()["wait_after_minutes"] is None
    method_id = created.json()["id"]

    updated = await client.put(
        f"{base}/{method_id}", json={"name": {"enGB": "Curing"}, "wait_after_minutes": 720}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["wait_after_minutes"] == 720

    read = await client.get(f"{base}/{method_id}")
    assert read.status_code == 200, read.text
    assert read.json()["wait_after_minutes"] == 720

    cleared = await client.put(f"{base}/{method_id}", json={"name": {"enGB": "Curing"}})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["wait_after_minutes"] is None


@pytest.mark.parametrize("base", [FABRICATION, INSPECTION])
async def test_a_negative_wait_is_refused(client, base: str) -> None:
    response = await client.post(
        f"{base}/", json={"name": {"enGB": "Curing"}, "wait_after_minutes": -1}
    )
    assert response.status_code == 422, response.text
