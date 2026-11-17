"""
HTTP round trips for a production order's first start and its interruption
trail: a resume keeps actual_start, canceling a paused order closes its
interruption, which also proves the cancel route has the interruption
repository wired in, and the lots list explains a resumed order by its latest
resume, because the orders the lot repository attaches carry their
interruptions. The prerequisites are seeded through the real repositories by
the time-tracking module's helper.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.conftest import auth_headers
from tests.integration.test_api_production_order_time_tracking import _seed_lot_and_order

ORDERS_BASE = "/api/v1/web/production-orders"
LOTS_BASE = "/api/v1/web/production-lots"


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(
        username="interruptions-owner",
        email="interruptions-owner@example.com",
        permissions=[Permission.WRITE_PRODUCTION_ORDERS],
    )


@pytest.fixture
async def production_settings(db: Session) -> None:
    """The lots list reads the production settings for its explanations."""
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


class TestInterruptionsOverHttp:
    async def test_resume_returns_the_first_actual_start(
        self, db: Session, client, owner: User
    ) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-INT-1")
        headers = await auth_headers(owner)

        started = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert started.status_code == 200
        paused = await client.post(f"{ORDERS_BASE}/{order.id}/pause", json={}, headers=headers)
        assert paused.status_code == 200
        resumed = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert resumed.status_code == 200

        body = resumed.json()
        assert body["status"] == ProductionOrderStatus.IN_PROGRESS.value
        assert body["actual_start"] == started.json()["actual_start"]
        [interruption] = body["interruptions"]
        assert interruption["resumed_at"] is not None

    async def test_cancel_of_a_paused_order_closes_its_interruption(
        self, db: Session, client, owner: User
    ) -> None:
        _lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-INT-2")
        headers = await auth_headers(owner)

        started = await client.post(f"{ORDERS_BASE}/{order.id}/start", json={}, headers=headers)
        assert started.status_code == 200
        paused = await client.post(f"{ORDERS_BASE}/{order.id}/pause", json={}, headers=headers)
        assert paused.status_code == 200
        canceled = await client.post(
            f"{ORDERS_BASE}/{order.id}/cancel",
            json={"expected_edit_version": order.edit_version},
            headers=headers,
        )
        assert canceled.status_code == 200

        body = canceled.json()
        assert body["status"] == ProductionOrderStatus.CANCELED.value
        [interruption] = body["interruptions"]
        assert interruption["resumed_at"] is not None

    async def test_lots_list_explains_a_resumed_order_by_its_latest_resume(
        self, db: Session, client, owner: User, production_settings: None
    ) -> None:
        lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-INT-3")
        headers = await auth_headers(owner)
        for action in ("start", "pause", "start"):
            response = await client.post(
                f"{ORDERS_BASE}/{order.id}/{action}", json={}, headers=headers
            )
            assert response.status_code == 200
        # The run moves into the past: first start on 2 March, paused on the
        # 3rd, resumed on the 4th.
        await db.execute(
            update(ProductionOrderOrmModel)
            .where(ProductionOrderOrmModel.id == order.id)
            .values(actual_start=datetime(2026, 3, 2, 8, 0, tzinfo=UTC))
        )
        await db.execute(
            update(ProductionOrderInterruptionOrmModel)
            .where(ProductionOrderInterruptionOrmModel.production_order_id == order.id)
            .values(
                paused_at=datetime(2026, 3, 3, 10, 0, tzinfo=UTC),
                resumed_at=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
            )
        )
        await db.commit()

        listed = await client.get(f"{LOTS_BASE}/", headers=headers)

        assert listed.status_code == 200
        [summary] = [item for item in listed.json()["items"] if item["id"] == lot.id]
        [listed_order] = [
            po for position in summary["positions"] for po in position["production_orders"]
        ]
        assert listed_order["actual_start"].startswith("2026-03-02")
        assert listed_order["earliest_start_reason"] == "in_progress"
        assert listed_order["earliest_start_date"] == "2026-03-04"
