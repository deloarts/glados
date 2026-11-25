"""
The production setting internal_handoff_minutes through the web API: the
minutes between the end of an in-house position and the next in-house
order, 0 on a fresh install.
"""

import httpx
import pytest

from src.modules.platform.domain.value_objects.permission import Permission

# Autouse: seeds the production settings the endpoint reads.
from tests.integration.test_api_lot_source_approval import _seed_settings  # noqa: F401

SETTINGS_BASE = "/api/v1/web/admin/settings/production"


@pytest.fixture
async def client(auth_client) -> httpx.AsyncClient:
    return await auth_client([Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])


async def test_the_handoff_is_zero_by_default_and_round_trips(client: httpx.AsyncClient) -> None:
    resp = await client.get(SETTINGS_BASE)
    assert resp.status_code == 200, resp.text
    assert resp.json()["internal_handoff_minutes"] == 0

    resp = await client.put(SETTINGS_BASE, json={"internal_handoff_minutes": 45})
    assert resp.status_code == 200, resp.text
    assert resp.json()["internal_handoff_minutes"] == 45

    resp = await client.get(SETTINGS_BASE)
    assert resp.json()["internal_handoff_minutes"] == 45
    # A field the request leaves out keeps its value.
    assert resp.json()["response_time_days"] == 1


async def test_a_negative_handoff_is_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.put(SETTINGS_BASE, json={"internal_handoff_minutes": -1})
    assert resp.status_code == 422, resp.text
