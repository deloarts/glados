"""
HTTP-level coverage of both routes of /api/v1/web/production-schedule.
"""

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)

BASE = "/api/v1/web/production-schedule"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """Both routes on this router read the production admin-settings
    domain (weekly calendar template etc.); `_seed_admin_settings`
    (conftest.py) does not cover it. Mirrors InitDatabase's defaults."""
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


async def test_read_schedule_board_requires_authentication(client) -> None:
    resp = await client.get(f"{BASE}/", params={"date_from": "2026-08-01", "date_to": "2026-08-31"})
    assert resp.status_code == 401


async def test_read_schedule_board_empty(auth_client) -> None:
    """No production orders seeded: the board resolves to an empty,
    well-shaped response rather than erroring, proving the route, DI
    graph and admin-settings read all work end to end."""
    client = await auth_client(permissions=[])
    resp = await client.get(f"{BASE}/", params={"date_from": "2026-08-01", "date_to": "2026-08-31"})
    assert resp.status_code == 200
    body = resp.json()
    assert "machines" in body


async def test_read_schedule_board_rejects_missing_date_range(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get(f"{BASE}/")
    assert resp.status_code == 422


async def test_auto_plan_requires_write_permission(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.post(f"{BASE}/auto-plan", json={})
    assert resp.status_code == 403


async def test_auto_plan_rejects_unknown_field(auth_client) -> None:
    """AutoPlanRequest is extra="forbid" to catch stale/unknown field
    renames as schema validation errors (422), not silent ignores. 422
    fires before the 403 permission check would, so this still needs
    write:production_orders to isolate the case under test."""
    client = await auth_client(permissions=["write:production_orders"])
    resp = await client.post(f"{BASE}/auto-plan", json={"assign_pool_machines": True})
    assert resp.status_code == 422


async def test_auto_plan_with_no_eligible_orders_is_a_noop(auth_client) -> None:
    """No QUEUED orders exist in this throwaway DB: AutoPlan resolves to an
    empty diff rather than erroring."""
    client = await auth_client(permissions=["write:production_orders"])
    resp = await client.post(f"{BASE}/auto-plan", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposals"] == []
    # AutoPlanResult.skipped (candidates the placement loop declined to
    # place: waiting_on_material/no_eligible_machine/no_eligible_pool)
    # defaults to an empty list, present on every response shape.
    assert body["skipped"] == []
