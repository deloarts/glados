"""
The booking quality view over HTTP: an order left running overnight, a final
completion without an assessment, and the manual pauses without a cause,
read through the real repositories on SQLite. The default week works Monday
to Friday from 08:00 for eight hours in the tenant's zone. The orders are
seeded with the stored status and times the view reads and without the
completion rows a completion would write, so the lifecycle drift check is
waived for this module.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.manufacturing_assessment_model import (
    ManufacturingAssessmentOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE
from tests.integration import _lifecycle_seed as seed

ZONE = ZoneInfo(SERVER_DEFAULT_TIMEZONE)
URL = "/api/v1/web/production-kpi/booking-quality"
PERIOD = {"date_from": "2026-03-02", "date_to": "2026-03-08"}

pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=ZONE)


async def _completed(db: AsyncSession, start: datetime, end: datetime, *, assessed: bool) -> int:
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "internal", "in_progress")
    order = await seed.production_order(
        db,
        position,
        "completed",
        quantity_completed=10.0,
        actual_start=start,
        actual_end=end,
        first_started_operator_id=1,
    )
    if assessed:
        await seed.add(
            db,
            ManufacturingAssessmentOrmModel(
                created=end,
                production_order_id=order.id,
                operator_id=1,
                actual_minutes_per_piece=3.5,
                complexity="normal",
            ),
        )
    return order.id


async def _pause(db: AsyncSession, order_id: int, at: datetime, cause: str | None) -> None:
    await seed.add(
        db,
        ProductionOrderInterruptionOrmModel(
            created=at,
            production_order_id=order_id,
            paused_at=at,
            resumed_at=at.replace(minute=30),
            paused_by_id=1,
            resumed_by_id=1,
            paused_operator_id=1,
            reason="manual",
            ended_by="resume",
            pause_cause=cause,
        ),
    )


async def test_the_view_reports_each_finding(db: AsyncSession, auth_client) -> None:
    # Started Tuesday 14:00 and completed Wednesday 10:00: sixteen hours of
    # the twenty booked fall outside the day shift.
    overnight = await _completed(db, _at(3, 14), _at(4, 10), assessed=True)
    unassessed = await _completed(db, _at(5, 8), _at(5, 12), assessed=False)
    await _pause(db, unassessed, _at(5, 9), None)
    await _pause(db, unassessed, _at(5, 10), "machine_fault")
    await db.commit()
    client = await auth_client(permissions=[])

    response = await client.get(URL, params=PERIOD)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["orders_with_bookings"] == 2
    [outside] = body["outside_working_time"]
    assert (outside["order_id"], outside["outside_minutes"]) == (overnight, 960)
    assert body["final_completions"] == 2
    assert [row["order_id"] for row in body["missing_assessments"]] == [unassessed]
    assert body["manual_pauses"] == 2
    assert [row["order_id"] for row in body["uncaused_pauses"]] == [unassessed]


async def test_bookings_outside_the_period_are_left_out(db: AsyncSession, auth_client) -> None:
    await _completed(db, _at(9, 8), _at(9, 12), assessed=False)
    await db.commit()
    client = await auth_client(permissions=[])

    body = (await client.get(URL, params=PERIOD)).json()

    assert (body["orders_with_bookings"], body["final_completions"]) == (0, 0)
