"""
The default calendar over HTTP: anyone signed in reads it, and saving it
needs the right to edit machines, not the settings right.
"""

from typing import Any

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401

URL = f"{API_WEB}/production-machines/default-working-hours"
# Every weekday must be named; the weekend has no working time.
WEEK = {str(day): [{"start": "06:00", "minutes": 480}] if day < 5 else [] for day in range(7)}


async def test_default_calendar_saves_with_the_machines_right(auth_client: Any) -> None:
    writer = await auth_client(permissions=[Permission.WRITE_MACHINES])

    r = await writer.put(URL, json={"weekly_hours": WEEK})
    assert r.status_code == 200, r.text

    reread = await writer.get(URL)
    assert reread.status_code == 200, reread.text
    assert reread.json()["0"] == [{"start": "06:00", "minutes": 480}]
    assert reread.json()["6"] == []


async def test_default_calendar_refuses_the_settings_right_alone(auth_client: Any) -> None:
    settings_admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

    r = await settings_admin.put(URL, json={"weekly_hours": WEEK})
    assert r.status_code == 403
