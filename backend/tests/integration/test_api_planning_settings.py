"""
The planning settings over HTTP: read and written behind the settings
permissions, validated on their bounds, and booking_quality_since never
written by a client. The combined settings read is covered with the other
sections in test_api_admin_settings_reads.py.
"""

from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings"


async def test_the_planning_settings_read_their_seeded_values(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    response = await client.get(f"{BASE}/planning")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["commit_horizon_working_days"], body["plan_retention_days"]) == (5, 400)
    assert body["booking_quality_since"].startswith("2000-01-01")


async def test_an_update_keeps_the_fields_it_leaves_out(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])

    response = await client.put(f"{BASE}/planning", json={"commit_horizon_working_days": 10})

    assert response.status_code == 200, response.text
    body = (await client.get(f"{BASE}/planning")).json()
    assert (body["commit_horizon_working_days"], body["plan_retention_days"]) == (10, 400)


async def test_booking_quality_since_cannot_be_written(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])

    await client.put(f"{BASE}/planning", json={"booking_quality_since": "2026-01-01T00:00:00Z"})

    body = (await client.get(f"{BASE}/planning")).json()
    assert body["booking_quality_since"].startswith("2000-01-01")


async def test_values_outside_their_bounds_are_refused(auth_client) -> None:
    client = await auth_client(permissions=[Permission.WRITE_SETTINGS])

    horizon = await client.put(f"{BASE}/planning", json={"commit_horizon_working_days": 0})
    retention = await client.put(f"{BASE}/planning", json={"plan_retention_days": 5})

    assert (horizon.status_code, retention.status_code) == (422, 422)


async def test_writing_needs_write_settings(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    response = await client.put(f"{BASE}/planning", json={"commit_horizon_working_days": 6})

    assert response.status_code == 403
