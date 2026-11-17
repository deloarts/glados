"""
HTTP-level round trip for the machine downtime endpoints: add, list,
update, end, delete, and the open_downtime badge denormalized onto the
machine list/detail responses. The machine prerequisite is seeded
directly through the real repository, the same pattern
test_api_production_order_time_tracking.py uses; only the router under
test goes through HTTP.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.conftest import auth_headers

MACHINES_BASE = "/api/v1/web/production-machines"


async def _seed_machine(db: Session, creator_id: int, internal_name: str) -> ProductionMachine:
    saved = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=datetime.now(UTC).date(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=internal_name,
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


@pytest.fixture
async def operator(create_user) -> User:
    return await create_user(
        username="downtime-operator",
        email="downtime-operator@example.com",
        permissions=[Permission.WRITE_MACHINES],
    )


@pytest.fixture
async def viewer(create_user) -> User:
    return await create_user(
        username="downtime-viewer", email="downtime-viewer@example.com", permissions=[]
    )


class TestAddEndDowntimeRoundTrip:
    async def test_add_shows_up_as_open_downtime_and_end_clears_it(
        self, db: Session, client, operator: User
    ) -> None:
        machine = await _seed_machine(db, operator.id, "DT-MILL-1")
        headers = await auth_headers(operator)

        added = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T08:00:00Z",
                "reason": MachineDowntimeReason.BREAKDOWN.value,
                "note": "Spindle fault",
            },
            headers=headers,
        )
        assert added.status_code == 201
        body = added.json()
        assert body["machine_id"] == machine.id
        assert body["ended_at"] is None
        assert body["reason"] == MachineDowntimeReason.BREAKDOWN.value
        downtime_id = body["id"]

        detail = await client.get(f"{MACHINES_BASE}/{machine.id}", headers=headers)
        assert detail.status_code == 200
        open_downtime = detail.json()["open_downtime"]
        assert open_downtime is not None
        assert open_downtime["id"] == downtime_id
        assert open_downtime["reason"] == MachineDowntimeReason.BREAKDOWN.value

        listing = await client.get(MACHINES_BASE, headers=headers)
        assert listing.status_code == 200
        row = next(m for m in listing.json()["items"] if m["id"] == machine.id)
        assert row["open_downtime"]["id"] == downtime_id

        ended = await client.post(
            f"{MACHINES_BASE}/downtimes/{downtime_id}/end",
            json={"ended_at": "2026-01-01T12:00:00Z"},
            headers=headers,
        )
        assert ended.status_code == 200
        ended_body = ended.json()
        assert ended_body["ended_at"] is not None
        assert ended_body["ended_by_id"] == operator.id

        detail_after_end = await client.get(f"{MACHINES_BASE}/{machine.id}", headers=headers)
        assert detail_after_end.json()["open_downtime"] is None

    async def test_ending_an_ended_downtime_again_is_refused(
        self, db: Session, client, operator: User
    ) -> None:
        machine = await _seed_machine(db, operator.id, "DT-MILL-END")
        headers = await auth_headers(operator)
        added = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T08:00:00Z",
                "reason": MachineDowntimeReason.BREAKDOWN.value,
            },
            headers=headers,
        )
        end_url = f"{MACHINES_BASE}/downtimes/{added.json()['id']}/end"
        first = await client.post(
            end_url, json={"ended_at": "2026-01-01T12:00:00Z"}, headers=headers
        )
        assert first.status_code == 200

        second = await client.post(
            end_url, json={"ended_at": "2026-01-01T15:00:00Z"}, headers=headers
        )

        assert second.status_code == 409
        assert second.json()["code"] == "MachineDowntimeAlreadyEndedError"
        listed = await client.get(
            f"{MACHINES_BASE}/downtimes", params={"machine_id": machine.id}, headers=headers
        )
        (row,) = listed.json()["items"]
        assert row["ended_at"].startswith("2026-01-01T12:00:00")
        assert len(row["changes"]) == 2

    async def test_second_open_downtime_on_same_machine_is_rejected(
        self, db: Session, client, operator: User
    ) -> None:
        machine = await _seed_machine(db, operator.id, "DT-MILL-2")
        headers = await auth_headers(operator)

        first = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T08:00:00Z",
                "reason": MachineDowntimeReason.NO_OPERATOR.value,
            },
            headers=headers,
        )
        assert first.status_code == 201

        second = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-02T08:00:00Z",
                "reason": MachineDowntimeReason.NO_MATERIAL.value,
            },
            headers=headers,
        )
        assert second.status_code == 409

    async def test_invalid_range_is_rejected(self, db: Session, client, operator: User) -> None:
        machine = await _seed_machine(db, operator.id, "DT-MILL-3")
        headers = await auth_headers(operator)

        response = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T12:00:00Z",
                "ended_at": "2026-01-01T08:00:00Z",
                "reason": MachineDowntimeReason.OTHER.value,
            },
            headers=headers,
        )
        assert response.status_code == 422

    async def test_unprivileged_user_cannot_add_downtime(
        self, db: Session, client, viewer: User, operator: User
    ) -> None:
        machine = await _seed_machine(db, operator.id, "DT-MILL-4")
        response = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T08:00:00Z",
                "reason": MachineDowntimeReason.OTHER.value,
            },
            headers=await auth_headers(viewer),
        )
        assert response.status_code == 403


class TestUpdateAndDeleteDowntime:
    async def test_update_and_delete_round_trip(self, db: Session, client, operator: User) -> None:
        machine = await _seed_machine(db, operator.id, "DT-MILL-5")
        headers = await auth_headers(operator)

        added = await client.post(
            f"{MACHINES_BASE}/downtimes",
            json={
                "machine_id": machine.id,
                "started_at": "2026-01-01T08:00:00Z",
                "ended_at": "2026-01-01T09:00:00Z",
                "reason": MachineDowntimeReason.MAINTENANCE.value,
            },
            headers=headers,
        )
        downtime_id = added.json()["id"]

        updated = await client.put(
            f"{MACHINES_BASE}/downtimes/{downtime_id}",
            json={
                "started_at": "2026-01-01T08:00:00Z",
                "ended_at": "2026-01-01T10:00:00Z",
                "reason": MachineDowntimeReason.TOOLING.value,
                "note": "Extended for tooling swap",
            },
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["reason"] == MachineDowntimeReason.TOOLING.value
        assert updated.json()["note"] == "Extended for tooling swap"

        listed = await client.get(
            f"{MACHINES_BASE}/downtimes", params={"machine_id": machine.id}, headers=headers
        )
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        deleted = await client.delete(f"{MACHINES_BASE}/downtimes/{downtime_id}", headers=headers)
        assert deleted.status_code == 204

        listed_after_delete = await client.get(
            f"{MACHINES_BASE}/downtimes", params={"machine_id": machine.id}, headers=headers
        )
        assert listed_after_delete.json()["total"] == 0

    async def test_not_found_returns_404(self, db: Session, client, operator: User) -> None:
        headers = await auth_headers(operator)
        response = await client.delete(f"{MACHINES_BASE}/downtimes/999999", headers=headers)
        assert response.status_code == 404


async def test_naive_times_are_read_as_utc(db: Session, client, operator: User) -> None:
    machine = await _seed_machine(db, operator.id, "DT-MILL-NAIVE")
    headers = await auth_headers(operator)
    closed = await client.post(
        f"{MACHINES_BASE}/downtimes",
        json={
            "machine_id": machine.id,
            "started_at": "2026-01-01T08:00:00Z",
            "ended_at": "2026-01-01T10:00:00Z",
            "reason": MachineDowntimeReason.BREAKDOWN.value,
        },
        headers=headers,
    )
    assert closed.status_code == 201, closed.text

    overlapping = await client.post(
        f"{MACHINES_BASE}/downtimes",
        json={
            "machine_id": machine.id,
            "started_at": "2026-01-01T09:00:00",
            "reason": MachineDowntimeReason.BREAKDOWN.value,
        },
        headers=headers,
    )
    added = await client.post(
        f"{MACHINES_BASE}/downtimes",
        json={
            "machine_id": machine.id,
            "started_at": "2026-01-01T11:00:00",
            "reason": MachineDowntimeReason.BREAKDOWN.value,
        },
        headers=headers,
    )
    assert added.status_code == 201, added.text
    ended = await client.post(
        f"{MACHINES_BASE}/downtimes/{added.json()['id']}/end",
        json={"ended_at": "2026-01-01T12:00:00"},
        headers=headers,
    )

    assert overlapping.status_code == 409, overlapping.text
    assert ended.status_code == 200, ended.text
    assert ended.json()["ended_at"].startswith("2026-01-01T12:00:00")
