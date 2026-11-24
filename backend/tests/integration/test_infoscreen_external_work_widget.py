"""
The infoscreen widget of external work against the throwaway SQLite
database: the parts that still have to leave for a supplier, by their
latest pickup, with the overdue ones only when asked, without the parts
already handed over, and narrowed to parts on an order when asked. The
dates the schedule walk writes are set on the rows directly.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_provision_model import (
    LotPositionProvisionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._lot_facts import give_lot_facts
from tests.integration._tenant_day import tenant_today
from tests.integration._terminal_helpers import seed_production
from tests.integration._terminal_helpers import seed_security
from tests.integration.test_infoscreen_widgets_second_set import _lot
from tests.integration.test_infoscreen_widgets_second_set import _made_item
from tests.integration.test_infoscreen_widgets_second_set import _project
from tests.integration.test_infoscreen_widgets_second_set import _screen


@pytest.fixture(autouse=True)
async def _settings(db: AsyncSession) -> None:
    await seed_security(db)
    await seed_production(db)


@pytest.fixture
async def writer(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[Permission.WRITE_INFOSCREENS, Permission.WRITE_FABRICATION_METHODS],
        username="writer",
        email="writer@example.com",
    )


async def _external(db: AsyncSession, lot: Any, latest_offset: int, **values: Any) -> Any:
    today = tenant_today()
    return await seed.position(
        db,
        lot,
        values.pop("kind", "external"),
        values.pop("status", "pending"),
        latest_pickup_date=today + timedelta(days=latest_offset),
        latest_delivery_date=today + timedelta(days=latest_offset + 4),
        **values,
    )


async def _outsourced_method(writer: httpx.AsyncClient) -> int:
    created = await writer.post(
        "/api/v1/web/fabrication-methods/",
        json={"name": {"enGB": "Hardening (widget test)"}, "required_external": True},
    )
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


@pytest.fixture
async def scenario(db: AsyncSession, writer: httpx.AsyncClient) -> dict[str, Any]:
    """One lot with four outside steps: overdue by three days and due in
    two days, both on a supplier's draft order, due in five days without a
    supplier yet, and one handed over already."""
    method_id = await _outsourced_method(writer)
    item = await _made_item(db, None)
    project = await _project(db, "P-EXT-WIDGET")
    lot = await _lot(db, "draft", item.id, project.id)
    purchase = await seed.order(db, "draft")
    overdue = await _external(db, lot, -3, sequence=1)
    await seed.line(db, purchase, "pending", at=overdue)
    ordered = await _external(db, lot, 2, sequence=2)
    await seed.line(db, purchase, "pending", at=ordered)
    later = await _external(db, lot, 5, sequence=3, kind="unassigned")
    db.add(
        LotStepOrmModel(
            created=seed.NOW,
            sequence=3,
            creator_id=1,
            fabrication_method_id=method_id,
            lot_id=lot.id,
            position_id=later.id,
            role="fabrication",
        )
    )
    gone = await _external(db, lot, 1, sequence=4)
    await seed.line(db, purchase, "pending", at=gone)
    db.add(
        LotPositionProvisionOrmModel(
            created=seed.NOW,
            lot_position_id=gone.id,
            quantity=10.0,
            provision_date=tenant_today(),
            creator_id=1,
        )
    )
    await give_lot_facts(db, lot.id)
    await db.commit()
    return {"lot": lot, "overdue": overdue, "ordered": ordered, "later": later}


async def test_the_widget_lists_what_must_leave_by_latest_pickup(
    scenario: dict[str, Any], writer: httpx.AsyncClient
) -> None:
    [data] = await _screen(writer, {"type": "external_work"})

    assert data["type"] == "external_work"
    offsets = [(row["latest_pickup_date"], row["alert"], row["days_late"]) for row in data["rows"]]
    today = tenant_today()
    assert offsets == [
        ((today - timedelta(days=3)).isoformat(), "overdue", 3),
        ((today + timedelta(days=2)).isoformat(), None, None),
        ((today + timedelta(days=5)).isoformat(), None, None),
    ]
    row = data["rows"][0]
    assert row["lot_number"] == scenario["lot"].lot_number
    assert row["part_number"] == "MD-100"
    assert row["due_back_date"] == (today + timedelta(days=1)).isoformat()


async def test_the_horizon_and_the_overdue_switch_narrow_the_rows(
    scenario: dict[str, Any], writer: httpx.AsyncClient
) -> None:
    short, no_overdue = await _screen(
        writer,
        {"type": "external_work", "horizon_days": 3},
        {"type": "external_work", "show_overdue": False},
    )

    assert len(short["rows"]) == 2
    assert all(row["alert"] != "overdue" for row in no_overdue["rows"])
    assert len(no_overdue["rows"]) == 2


async def test_only_with_supplier_shows_the_parts_on_an_order(
    scenario: dict[str, Any], writer: httpx.AsyncClient
) -> None:
    [data] = await _screen(writer, {"type": "external_work", "only_with_supplier": True})

    assert [row["supplier_suggested"] for row in data["rows"]] == [False, False]


async def test_the_layout_is_kept_and_checked(writer: httpx.AsyncClient) -> None:
    created = await writer.post(
        "/api/v1/web/infoscreens/",
        json={
            "name": "Lanes",
            "pages": [
                {"layout": "full", "slots": [{"type": "external_work", "layout": "suppliers"}]}
            ],
        },
    )
    rejected = await writer.post(
        "/api/v1/web/infoscreens/",
        json={
            "name": "Wrong",
            "pages": [{"layout": "full", "slots": [{"type": "external_work", "layout": "rows"}]}],
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["pages"][0]["slots"][0]["layout"] == "suppliers"
    assert rejected.status_code == 422
