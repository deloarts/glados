"""
HTTP-level coverage of POST /api/v1/web/production-schedule/auto-plan/stream:
the SSE-streaming sibling of POST /auto-plan (see
test_api_production_schedule.py). Proves the plain error paths
(401/403/422) stay ordinary HTTP responses with no stream opened, that a
zero-candidate run's terminal `result` frame is byte-identical to the
plain endpoint's response body for the same state, and that a seeded
candidate is actually placed and committed to the DB via the stream's
worker thread, which opens its own SessionLocal() rather than reusing the
request-scoped session so committed writes are visible once the thread
finishes.

This stream is FINITE (ends right after its terminal frame), so plain
TestClient.post(...) works fine and returns the whole SSE body as text;
unlike live.py's genuinely-infinite stream, no raw-ASGI harness is needed
here (see test_api_live_stream.py's module docstring for why THAT one
needs it).

This file also covers the app-wide "one run at a time" mutex: the
409-on-second-run path, the
GET .../auto-plan/status endpoint, mutex release after both a normal and
a FAILING run, and the degraded-Redis path. Those new tests replace
`get_async_redis_client()` in both the run-registry module and this endpoint
module with an in-memory fake (extending the one test_autoplan_run_
registry.py already built for the same purpose) rather than touching the
real Redis instance test_api_login_lockout.py's module docstring notes
the integration suite is designed to run without. A real server may
happen to be reachable from wherever this runs, but nothing here may
depend on that.
"""

import inspect
import json
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    build_auto_plan_use_case as _real_build_auto_plan_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints import (
    production_schedule as stream_module,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.infrastructure import autoplan_run_registry as registry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.live_signal import LiveResource
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.unit.test_autoplan_run_registry import FakeRedis as RegistryFakeRedis

BASE = "/api/v1/web/production-schedule"
STREAM = f"{BASE}/auto-plan/stream"
STATUS = f"{BASE}/auto-plan/status"


@pytest.fixture(autouse=True)
async def _seed_production_settings(db: Session) -> None:
    """Mirrors test_api_production_schedule.py's own autouse fixture: both
    auto-plan routes read the production admin-settings domain (weekly
    calendar template etc.), which `_seed_admin_settings` (conftest.py)
    does not cover."""
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


def _parse_sse_frames(text: str) -> list[tuple[str, str]]:
    """Minimal parser for this endpoint's SSE body: `event:`/`data:` lines
    separated by a blank line make one (event, data) pair; comment/ping
    lines (starting with `:`, sse-starlette's keep-alive frames) are
    ignored, same stance the wire contract asks clients to take. Not a
    general SSE parser; this endpoint never sends multi-line data."""
    frames: list[tuple[str, str]] = []
    event: str | None = None
    data_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        if line == "":
            if event is not None:
                frames.append((event, "\n".join(data_lines)))
            event = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
    if event is not None:
        frames.append((event, "\n".join(data_lines)))
    return frames


async def _make_item(db: Session, creator_id: int) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name="Auto-plan stream part",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    return seeded


async def _seed_order_on_machine(
    db: Session, creator_id: int
) -> tuple[ProductionOrder, ProductionMachine]:
    """A QUEUED order already assigned to a machine: with
    AutoPlanCommand.assign_machines defaulting to False, an order is only
    ever re-sequenced within the machine it's already on (see
    resolve_eligible_machine_ids rule 3), so this is the minimal seed that
    still makes it an eligible, placeable candidate; a truly unassigned
    order would be left untouched instead."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number="P-APS-1")
    )
    made_item = await _make_item(db, creator_id)
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number="LN-APS-1",
            quantity=10.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
            # A rework/alteration lot (is_alteration=True) is never gated
            # on raw-material arrival at all (scheduling.
            # is_unplannable_for_missing_material via _context.
            # _resolve_raw_material_arrived); this test is exercising
            # machine re-sequencing/placement, not material timing, and
            # needs this order to actually place. Any real MadeItem id
            # satisfies the FK; self-referencing this lot's own made item
            # is the simplest one already in hand.
            source_made_item_id=made_item.id,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    machine = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            internal_name="APS-MILL-1",
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    order = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number="PO-APS-STREAM-1",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=1,
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine.id,
            lot_position_id=position.id,
        )
    )
    await db.commit()
    return order, machine


@pytest.fixture
async def owner(create_user) -> User:
    return await create_user(username="aps-owner", email="aps-owner@example.com")


# ── Plain HTTP error paths: no stream is ever opened ────────────────────


async def test_stream_requires_authentication(client) -> None:
    resp = await client.post(STREAM, json={})
    assert resp.status_code == 401
    assert not resp.headers.get("content-type", "").startswith("text/event-stream")


async def test_stream_requires_write_permission(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.post(STREAM, json={})
    assert resp.status_code == 403
    assert not resp.headers.get("content-type", "").startswith("text/event-stream")


async def test_stream_rejects_unknown_field(auth_client) -> None:
    """Mirrors test_auto_plan_rejects_unknown_field: 422 (schema
    validation, AutoPlanRequest is extra='forbid') fires before the 403
    permission check would, so write:production_orders isolates the case
    under test."""
    client = await auth_client(permissions=["write:production_orders"])
    resp = await client.post(STREAM, json={"assign_pool_machines": True})
    assert resp.status_code == 422
    assert not resp.headers.get("content-type", "").startswith("text/event-stream")


# ── Zero-candidate run: stage frames + result identical to /auto-plan ──


async def test_stream_no_eligible_orders_matches_plain_endpoint(auth_client) -> None:
    client = await auth_client(permissions=["write:production_orders"])

    plain_resp = await client.post(f"{BASE}/auto-plan", json={})
    assert plain_resp.status_code == 200
    expected = plain_resp.json()
    assert expected["proposals"] == []
    assert expected["skipped_pinned_or_in_progress"] == 0
    assert expected["skipped_todays_planned"] == 0

    stream_resp = await client.post(STREAM, json={})
    assert stream_resp.status_code == 200
    assert stream_resp.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse_frames(stream_resp.text)
    error_frames = [f for f in frames if f[0] == "error"]
    assert error_frames == []

    progress = [json.loads(data) for event, data in frames if event == "progress"]
    stages = [p["stage"] for p in progress]
    assert stages == [
        "preparing",
        "loading_orders",
        "scoring",
        "placing",
        "recomputing",
        "finalizing",
    ]
    placing = next(p for p in progress if p["stage"] == "placing")
    assert placing["current"] == 0
    assert placing["total"] == 0
    assert placing["order"] is None
    recomputing = next(p for p in progress if p["stage"] == "recomputing")
    assert recomputing["current"] == 0
    assert recomputing["total"] == 0

    result_frames = [data for event, data in frames if event == "result"]
    assert len(result_frames) == 1
    assert json.loads(result_frames[0]) == expected


# ── Seeded candidate: placing frame carries the order, DB is committed ──


async def test_stream_seeded_candidate_places_and_commits(
    db: Session, auth_client, owner: User
) -> None:
    order, machine = await _seed_order_on_machine(db, owner.id)
    client = await auth_client(permissions=["write:production_orders"])

    resp = await client.post(STREAM, json={})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse_frames(resp.text)
    error_frames = [f for f in frames if f[0] == "error"]
    assert error_frames == []

    progress = [json.loads(data) for event, data in frames if event == "progress"]
    placing_with_order = [
        p for p in progress if p["stage"] == "placing" and p.get("order") is not None
    ]
    assert len(placing_with_order) == 1
    order_event = placing_with_order[0]["order"]
    assert order_event["order_id"] == order.id
    assert order_event["production_order_number"] == "PO-APS-STREAM-1"
    assert order_event["placed"] is True
    assert order_event["before_machine_id"] == machine.id
    assert order_event["after_machine_id"] == machine.id
    # made_item_revision: denormalized alongside made_item_part_number
    # on this live-progress frame the same way it is on the /result proposal
    # below. _make_item seeds revision="0".
    assert order_event["made_item_revision"] == "0"

    result_frames = [data for event, data in frames if event == "result"]
    assert len(result_frames) == 1
    result = json.loads(result_frames[0])
    assert len(result["proposals"]) == 1
    proposal = result["proposals"][0]
    assert proposal["order_id"] == order.id
    assert proposal["after_machine_id"] == machine.id
    assert proposal["made_item_revision"] == "0"

    db.expire_all()
    refreshed = await SqlAlchemyProductionOrderRepository(db).get_by_id(order.id)
    assert refreshed is not None
    assert refreshed.machine_id == machine.id
    assert refreshed.queue_sequence >= 1


# ── Mutex + status ───────────────────────────────────────────────────────


async def _resolved(value):
    return await value if inspect.isawaitable(value) else value


class FakeRedis(RegistryFakeRedis):
    """Adds PUBLISH to the run-registry's own fake (SET/GET/DEL/EVAL,
    itself layered on test_event_bus.FakeRedis's XADD/`fail`), so one
    instance can stand in for `get_async_redis_client()` in both places this
    feature calls it: the registry module's mutex/heartbeat/read, and
    this endpoint module's own `_publish_run_signal` (the `auto-plan-run`
    live signal)."""

    def __init__(self, fail: bool = False) -> None:
        super().__init__(fail=fail)
        self.published: list[tuple[str, str]] = []

    # The registry and this endpoint await every command on the async client.
    # The base fake may still answer SET/GET/EVAL synchronously, so these
    # await its answer only when it is awaitable.
    async def set(self, name, value, nx=False, px=None):
        return await _resolved(super().set(name, value, nx=nx, px=px))

    async def get(self, name):
        return await _resolved(super().get(name))

    async def eval(self, script, numkeys, *keys_and_args):
        return await _resolved(super().eval(script, numkeys, *keys_and_args))

    async def publish(self, channel, message):
        self.commands.append("PUBLISH")
        self._maybe_fail()
        self.published.append((channel, message))
        return 1


class _BrokenAutoPlanUseCase:
    """Stands in for `build_auto_plan_use_case`'s return value to force an
    exception from inside the worker thread, after the mutex is already
    held: the specific case the "released after a FAILING run" test
    below exists to catch (a botched `finally` would strand the lock)."""

    async def execute(self, *, actor, cmd, progress):
        raise RuntimeError("boom")


def _run_signals(fake: FakeRedis) -> list[dict]:
    """Flattens every publish() call into one list of signal dicts, in
    order; mirrors test_change_tracking.py's own `_signals` helper."""
    return [signal for _channel, payload in fake.published for signal in json.loads(payload)]


@pytest.fixture
def fake_redis(monkeypatch) -> FakeRedis:
    """Swaps `get_async_redis_client()` for an in-memory fake in both modules
    this feature touches, so the mutex/heartbeat/signal behaviour is
    exercised deterministically regardless of whether a real Redis
    happens to be reachable from wherever this suite runs. See this
    file's module docstring and test_api_login_lockout.py's."""
    fake = FakeRedis()
    monkeypatch.setattr(registry, "get_async_redis_client", lambda: fake)
    monkeypatch.setattr(stream_module, "get_async_redis_client", lambda: fake)
    return fake


# ── GET /auto-plan/status ────────────────────────────────────────────────


async def test_status_requires_authentication(client) -> None:
    resp = await client.get(STATUS)
    assert resp.status_code == 401


async def test_status_idle_when_no_run_active(fake_redis: FakeRedis, auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get(STATUS)
    assert resp.status_code == 200
    assert resp.json() == {"running": False, "run": None}


async def test_status_reports_the_mid_run_shape(
    fake_redis: FakeRedis, auth_client, owner: User
) -> None:
    handle = await registry.try_acquire(user_id=owner.id, user_name=owner.full_name)
    assert handle is not None
    registry.update_snapshot(handle, stage="scoring", current=2, total=5)
    await registry.heartbeat_once(handle)

    client = await auth_client(permissions=[])
    resp = await client.get(STATUS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is True
    run = body["run"]
    assert run["run_id"] == handle.run_id
    assert run["user_id"] == owner.id
    assert run["user_name"] == owner.full_name
    assert run["stage"] == "scoring"
    assert run["current"] == 2
    assert run["total"] == 5


# ── Mutex: a second run is refused, no stream opened ────────────────────


async def test_stream_returns_409_when_another_run_holds_the_mutex(
    fake_redis: FakeRedis, auth_client, owner: User
) -> None:
    handle = await registry.try_acquire(user_id=owner.id, user_name=owner.full_name)
    assert handle is not None

    client = await auth_client(permissions=["write:production_orders"])
    resp = await client.post(STREAM, json={})

    assert resp.status_code == 409
    assert not resp.headers.get("content-type", "").startswith("text/event-stream")
    assert resp.json()["code"] == "AutoPlanRunInProgressError"


# ── Mutex release + live signals ─────────────────────────────────────────


async def test_mutex_released_after_a_normal_run_and_signals_are_published(
    fake_redis: FakeRedis, auth_client
) -> None:
    client = await auth_client(permissions=["write:production_orders"])

    resp = await client.post(STREAM, json={})
    assert resp.status_code == 200
    frames = _parse_sse_frames(resp.text)
    assert [f for f in frames if f[0] == "error"] == []
    assert len([f for f in frames if f[0] == "result"]) == 1

    # Released: status is idle again, and a second run isn't refused.
    assert (await client.get(STATUS)).json() == {"running": False, "run": None}

    second_resp = await client.post(STREAM, json={})
    assert second_resp.status_code == 200
    second_frames = _parse_sse_frames(second_resp.text)
    assert [f for f in second_frames if f[0] == "error"] == []
    assert len([f for f in second_frames if f[0] == "result"]) == 1

    # Exactly the start + end refetch hints, on the auto-plan-run resource,
    # for each of the two runs above.
    signals = _run_signals(fake_redis)
    assert len(signals) == 4
    assert all(s["resource"] == LiveResource.AUTO_PLAN_RUN for s in signals)
    assert all(s["action"] == "updated" for s in signals)
    assert all(s["id"] == 0 for s in signals)


async def test_mutex_released_after_a_failing_run(
    fake_redis: FakeRedis, auth_client, monkeypatch
) -> None:
    monkeypatch.setattr(
        stream_module, "build_auto_plan_use_case", lambda db: _BrokenAutoPlanUseCase()
    )
    client = await auth_client(permissions=["write:production_orders"])

    resp = await client.post(STREAM, json={})
    assert resp.status_code == 200
    frames = _parse_sse_frames(resp.text)
    error_frames = [data for event, data in frames if event == "error"]
    assert len(error_frames) == 1
    assert json.loads(error_frames[0]) == {"detail": "Auto-plan failed."}
    assert [f for f in frames if f[0] == "result"] == []

    # Released even though the run itself blew up: the specific guard
    # against a botched `finally` stranding the lock.
    assert (await client.get(STATUS)).json() == {"running": False, "run": None}

    monkeypatch.setattr(stream_module, "build_auto_plan_use_case", _real_build_auto_plan_use_case)
    second_resp = await client.post(STREAM, json={})
    assert second_resp.status_code == 200
    second_frames = _parse_sse_frames(second_resp.text)
    assert [f for f in second_frames if f[0] == "error"] == []
    assert len([f for f in second_frames if f[0] == "result"]) == 1


# ── Redis unavailable: degrade to today's unguarded behaviour ───────────


async def test_stream_runs_to_completion_when_redis_is_unreachable(
    monkeypatch, auth_client
) -> None:
    fake = FakeRedis(fail=True)
    monkeypatch.setattr(registry, "get_async_redis_client", lambda: fake)
    monkeypatch.setattr(stream_module, "get_async_redis_client", lambda: fake)

    client = await auth_client(permissions=["write:production_orders"])
    resp = await client.post(STREAM, json={})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse_frames(resp.text)
    assert [f for f in frames if f[0] == "error"] == []
    assert len([f for f in frames if f[0] == "result"]) == 1
