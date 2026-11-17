"""
Unit tests for the event bus infrastructure: codec round-trips, the Redis
Streams transport the outbox relay publishes through, and the consumer
worker loop.
No Redis server, the client is replaced with in-memory fakes.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import pytest
import redis

from src.modules.catalogue.domain.events.bought_item_events import BoughtItemCreated
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemStatusChanged
from src.modules.catalogue.domain.events.bought_item_events import DemandItemCreated
from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemCreated
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemCreated
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemStatusChanged
from src.modules.catalogue.domain.events.source_item_events import SourceItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.domain.events.pdm_events import PdmFileIngested
from src.modules.external_data.domain.events.pdm_events import PdmIngestConflict
from src.modules.fulfillment.domain.events.lot_events import LotCanceled
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.events.lot_events import LotEndedShort
from src.modules.fulfillment.domain.events.lot_events import LotOnHold
from src.modules.fulfillment.domain.events.lot_events import LotPositionAssigned
from src.modules.fulfillment.domain.events.lot_events import LotPositionDeliveryRecorded
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotResumed
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeEnded
from src.modules.fulfillment.domain.events.machine_downtime_events import MachineDowntimeStarted
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolArchived
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolCreated
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolRestored
from src.modules.fulfillment.domain.events.machine_pool_events import MachinePoolUpdated
from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.events.order_events import OrderCanceled
from src.modules.fulfillment.domain.events.order_events import OrderCreated
from src.modules.fulfillment.domain.events.order_events import OrderItemDelivered
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderRequested
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderSubmitted
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineArchived,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineCreated
from src.modules.fulfillment.domain.events.production_machine_events import (
    ProductionMachineRestored,
)
from src.modules.fulfillment.domain.events.production_machine_events import ProductionMachineUpdated
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionRecorded,
)
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionReversed,
)
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderPaused
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderResumed
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderStarted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.events.quote_request_events import QuoteRequestStatusChanged
from src.modules.fulfillment.domain.events.schedule_events import ScheduleRecomputeRequested
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.adapters.outbound.external.event_bus.redis_stream_event_bus import (
    RedisStreamEventBus,
)
from src.modules.platform.domain.events.user_events import UserDeactivated
from src.modules.platform.domain.events.user_events import UserForcedLogout
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.infrastructure.events import worker as worker_module
from src.modules.platform.infrastructure.events.codec import EventCodecError
from src.modules.platform.infrastructure.events.codec import deserialize
from src.modules.platform.infrastructure.events.codec import serialize
from src.modules.platform.infrastructure.events.registry import EVENT_REGISTRY
from src.modules.platform.infrastructure.events.registry import EVENTS_STREAM
from src.modules.platform.infrastructure.events.worker import EventWorker
from src.modules.quality.domain.events.document_events import DocumentEditingEnded
from src.modules.quality.domain.events.document_events import DocumentEditingTakenOver
from src.modules.quality.domain.events.document_events import DocumentMarkedInvalid
from src.modules.quality.domain.events.document_events import DocumentRevised
from src.modules.quality.domain.events.printer_events import PrinterArchived
from src.modules.quality.domain.events.printer_events import PrinterCreated
from src.modules.quality.domain.events.printer_events import PrinterRestored
from src.modules.quality.domain.events.printer_events import PrinterUpdated
from src.modules.workspace.domain.events.meeting_events import MeetingActivityDue
from src.modules.workspace.domain.events.product_events import ProductCreated
from src.modules.workspace.domain.events.product_events import ProductUpdated
from src.modules.workspace.domain.events.project_events import ProjectCreated
from src.modules.workspace.domain.events.project_events import ProjectDeleted
from src.modules.workspace.domain.events.project_events import ProjectUpdated

# ── Codec ─────────────────────────────────────────────────────────────

EVENT_INSTANCES = [
    BoughtItemCreated(item_id=42, article_name="Resistor 10k", creator_id=7),
    BoughtItemStatusChanged(
        item_id=42,
        article_name="Resistor 10k",
        old_status=BoughtItemCatalogueStatus.ACTIVE,
        new_status=BoughtItemCatalogueStatus.REPLACED,
        actor_id=7,
    ),
    DemandItemCreated(demand_id=1, item_id=42, project_id=3, creator_id=7),
    DemandItemStatusChanged(
        demand_id=1,
        item_article_name="Resistor 10k",
        old_status=BoughtItemDemandStatus.ORDERED,
        new_status=BoughtItemDemandStatus.FULFILLED,
        actor_id=7,
        notify_on_delivery=True,
        creator_id=4,
        order_id=5,
        order_item_id=9,
    ),
    MadeItemCreated(item_id=43, article_name="Bracket", creator_id=7),
    MadeItemStatusChanged(
        item_id=43,
        article_name="Bracket",
        old_status=MadeItemCatalogueStatus.ACTIVE,
        new_status=MadeItemCatalogueStatus.REPLACED,
        actor_id=7,
    ),
    SourceItemStatusChanged(
        item_id=44,
        old_status=SourceItemCatalogueStatus.ACTIVE,
        new_status=SourceItemCatalogueStatus.INACTIVE,
        actor_id=7,
    ),
    SourceItemDemandStatusChanged(
        demand_id=3,
        lot_id=8,
        material_name="Aluminium Bar 20x20x1000",
        old_status=SourceItemDemandStatus.ORDERED,
        new_status=SourceItemDemandStatus.FULFILLED,
        actor_id=7,
        notify_on_delivery=True,
        creator_id=4,
    ),
    MadeItemDemandItemCreated(demand_id=1, made_item_id=43, project_id=3, creator_id=7),
    MadeItemDemandItemStatusChanged(
        demand_id=1,
        item_article_name="Bracket",
        old_status=MadeItemDemandStatus.ALLOCATED,
        new_status=MadeItemDemandStatus.FULFILLED,
        actor_id=7,
        notify_on_delivery=True,
        creator_id=4,
    ),
    OrderCreated(order_id=5, order_number="ORD-2026-001", creator_id=7, supplier_id=2),
    OrderRequested(order_id=5, order_number="ORD-2026-001", actor_id=7, supplier_id=2),
    OrderSubmitted(order_id=5, order_number="ORD-2026-001", actor_id=7, supplier_id=2),
    OrderCanceled(order_id=5, order_number="ORD-2026-001", actor_id=7, supplier_id=2, creator_id=4),
    OrderItemDelivered(
        order_item_id=9,
        order_id=5,
        bought_item_id=42,
        actor_id=7,
        source_item_id=None,
        quantity=3.0,
    ),
    DeliveryPiecesRejected(
        order_item_id=9,
        order_id=5,
        supplier_id=2,
        quantity=2.0,
        reason="Surface damage",
        outcome="redeliver",
        actor_id=7,
    ),
    LotCreated(lot_id=1, made_item_id=43, creator_id=7),
    LotCompleted(lot_id=1, lot_number="LOT-2026-0001", creator_id=7, made_item_id=43),
    LotCanceled(lot_id=1, lot_number="LOT-2026-0001", actor_id=7, creator_id=7),
    LotEndedShort(
        lot_id=1,
        lot_number="LOT-2026-0001",
        quantity=6.0,
        original_quantity=10.0,
        demand_ids=[3],
        actor_id=7,
    ),
    LotSupplierLinesToSettle(
        lot_id=1,
        lot_number="LOT-2026-0001",
        ended="canceled",
        open_lines=["B-2026-0003 pos. 2"],
        canceled_lines=[],
        order_id=3,
        actor_id=7,
    ),
    ScheduleRecomputeRequested(generation=4),
    LotPositionAssigned(lot_id=1, position_id=1, order_id=5, order_item_id=9, actor_id=7),
    LotPositionDeliveryRecorded(
        lot_id=1, position_id=1, order_item_id=9, quantity_completed=3.0, actor_id=7
    ),
    LotOnHold(lot_id=1, lot_number="LOT-2026-0001", actor_id=7, creator_id=7),
    LotResumed(lot_id=1, lot_number="LOT-2026-0001", actor_id=7, creator_id=7),
    LotStatusChanged(
        lot_id=1,
        lot_number="LOT-2026-0001",
        creator_id=7,
        old_status=LotStatus.PLANNED,
        new_status=LotStatus.IN_PROGRESS,
        actor_id=7,
    ),
    LotPositionStatusChanged(
        lot_id=1,
        position_id=1,
        old_status=LotPositionStatus.ORDERED_OR_QUEUED,
        new_status=LotPositionStatus.IN_PROGRESS,
        actor_id=7,
    ),
    PiecesScrapped(
        lot_id=1,
        lot_number="LOT-2026-0001",
        position_id=1,
        production_order_id=51,
        quantity=2.0,
        reason="Wrong bore diameter",
        replacement_lot_id=2,
        replacement_lot_number="LOT-2026-0002",
        actor_id=7,
        completion_id=81,
    ),
    ProductCreated(product_id=21, product_number="PR-100", actor_id=7, designated_user_id=4),
    ProductUpdated(
        product_id=21,
        product_number="PR-100",
        actor_id=7,
        designated_user_id=4,
        old_designated_user_id=7,
    ),
    ProjectCreated(project_id=11, project_number="P-100", actor_id=7, designated_user_id=4),
    ProjectUpdated(
        project_id=11,
        project_number="P-100",
        actor_id=7,
        designated_user_id=4,
        old_designated_user_id=7,
    ),
    ProjectDeleted(project_id=11, project_number="P-100", actor_id=7),
    ProductionMachineCreated(machine_id=31, internal_name="Mill 1", actor_id=7),
    ProductionMachineUpdated(machine_id=31, internal_name="Mill 1", actor_id=7),
    ProductionMachineArchived(machine_id=31, internal_name="Mill 1", actor_id=7),
    ProductionMachineRestored(machine_id=31, internal_name="Mill 1", actor_id=7),
    MachineDowntimeStarted(
        downtime_id=91, machine_id=31, reason="Spindle bearing failure", actor_id=7
    ),
    MachineDowntimeEnded(downtime_id=91, machine_id=31, actor_id=7),
    MachinePoolCreated(pool_id=71, name="Milling Machines", actor_id=7),
    MachinePoolUpdated(pool_id=71, name="Milling Machines", actor_id=7),
    MachinePoolArchived(pool_id=71, name="Milling Machines", actor_id=7),
    MachinePoolRestored(pool_id=71, name="Milling Machines", actor_id=7),
    ProductionOrderCreated(
        production_order_id=51,
        machine_id=31,
        lot_position_id=1,
        creator_id=7,
        machine_pool_id=None,
    ),
    ProductionOrderStarted(production_order_id=51, machine_id=31, actor_id=7, machine_pool_id=None),
    ProductionOrderPaused(production_order_id=51, actor_id=7),
    ProductionOrderResumed(production_order_id=51, actor_id=7, machine_id=31),
    ProductionOrderCompletionRecorded(
        production_order_id=51, lot_position_id=1, quantity_completed=3.0, actor_id=7
    ),
    ProductionOrderCompletionReversed(
        production_order_id=51, completion_id=4, reversal_id=5, actor_id=7
    ),
    ProductionOrderCompleted(production_order_id=51, machine_id=31, creator_id=7),
    ProductionOrderCanceled(production_order_id=51, actor_id=7, creator_id=7),
    ProductionOrderStatusChanged(
        production_order_id=51,
        old_status=ProductionOrderStatus.IN_PROGRESS,
        new_status=ProductionOrderStatus.COMPLETED,
        actor_id=7,
        creator_id=4,
    ),
    QuoteRequestStatusChanged(
        quote_request_id=12,
        request_number="RFQ-26-00012",
        creator_id=4,
        old_status=QuoteRequestStatus.AWARDED,
        new_status=QuoteRequestStatus.SENT,
        actor_id=7,
    ),
    OrderStatusChanged(
        order_id=5,
        order_number="ORD-2026-0005",
        supplier_id=3,
        creator_id=4,
        old_status=OrderStatus.ORDERED,
        new_status=OrderStatus.PARTIALLY_DELIVERED,
        actor_id=7,
    ),
    OrderItemStatusChanged(
        order_item_id=9,
        order_id=5,
        line_type=OrderLineType.MADE,
        lot_position_id=1,
        old_status=OrderItemStatus.ORDERED,
        new_status=OrderItemStatus.PARTIALLY_DELIVERED,
        actor_id=7,
    ),
    PrinterCreated(printer_id=61, name="Zebra ZT230", actor_id=7),
    PrinterUpdated(printer_id=61, name="Zebra ZT230", actor_id=7),
    PrinterArchived(printer_id=61, name="Zebra ZT230", actor_id=7),
    PrinterRestored(printer_id=61, name="Zebra ZT230", actor_id=7),
    UserPermissionsChanged(user_id=4, actor_id=7),
    UserDeactivated(user_id=4, actor_id=7),
    UserForcedLogout(user_id=4, actor_id=7),
    PdmFileChangeRequested(
        vault_name="demo-vault",
        file_id=1234,
        path=None,
        version=7,
        requested_by_id=7,
        source="retry",
        requested_by_name="Mira Holt",
    ),
    PdmFileIngested(
        vault_id="e2a87d6d-8f9f-4c1c-a40c-39b81d9f9f56",
        file_id=1234,
        kind="made",
        item_id=42,
        action="created",
        part_number="AB-123",
        revision="B",
    ),
    PdmIngestConflict(
        vault_id="e2a87d6d-8f9f-4c1c-a40c-39b81d9f9f56",
        file_id=1234,
        kind="bought",
        part_number="AB-124",
        reason="part number registered to another item",
    ),
    DocumentEditingTakenOver(
        resource="calculations",
        document_id=11,
        title="Bracket costing",
        previous_editor_id=4,
        actor_id=7,
        actor_name="Ada Admin",
    ),
    DocumentEditingEnded(
        resource="checklists",
        document_id=12,
        title="Final inspection",
        previous_editor_id=4,
        actor_id=7,
        actor_name="Ada Admin",
    ),
    DocumentMarkedInvalid(
        resource="calculations",
        document_id=11,
        title="Bracket costing",
        revision="B",
        reason="wrong material price",
        actor_id=7,
        actor_name="Ada Admin",
        recipient_ids=[4, 5],
    ),
    DocumentRevised(
        resource="checklists",
        document_id=12,
        title="Final inspection",
        revision="C",
        previous_revision="B",
        reason="new torque values",
        actor_id=7,
        actor_name="Ada Admin",
        recipient_ids=[4],
    ),
    BoughtItemEdpPictureRequested(item_id=42),
    MeetingActivityDue(
        meeting_id=9,
        meeting_number="MTG-26-00001",
        recipient_id=4,
        mention_count=2,
        todo_count=1,
        message="2 mentions and 1 todo in MTG-26-00001",
        title="Meeting activity",
    ),
]


def test_every_registered_event_has_a_round_trip_case():
    assert {type(e).__name__ for e in EVENT_INSTANCES} == set(EVENT_REGISTRY)


@pytest.mark.parametrize("event", EVENT_INSTANCES, ids=lambda e: type(e).__name__)
def test_codec_round_trip(event):
    fields = serialize(event)

    assert fields["type"] == type(event).__name__
    json.loads(fields["payload"])  # payload is one valid JSON document

    assert deserialize(fields) == event


def test_round_trip_rebuilds_enum_members():
    # str-enums compare equal to their raw value, so == alone can't catch a
    # decoder that leaves plain strings behind. Check the type explicitly.
    event = EVENT_INSTANCES[1]
    restored = deserialize(serialize(event))
    assert isinstance(restored.old_status, BoughtItemCatalogueStatus)
    assert isinstance(restored.new_status, BoughtItemCatalogueStatus)


def test_serialize_rejects_unregistered_event():
    @dataclass(frozen=True)
    class NotAnEvent:
        foo: int

    with pytest.raises(EventCodecError):
        serialize(NotAnEvent(foo=1))


def test_deserialize_rejects_unknown_type():
    with pytest.raises(EventCodecError):
        deserialize({"type": "Nope", "payload": "{}"})


def test_deserialize_rejects_missing_fields():
    with pytest.raises(EventCodecError):
        deserialize({"type": "ProjectCreated"})


def test_deserialize_rejects_corrupt_payload():
    with pytest.raises(EventCodecError):
        deserialize({"type": "ProjectCreated", "payload": "not json"})


# ── Relay transport ───────────────────────────────────────────────────


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        if self.fail:
            raise redis.ConnectionError("redis is down")
        self.calls.append((stream, fields))
        return "1-0"


async def test_publish_raw_writes_the_outbox_fields_to_the_stream():
    fake = FakeRedis()
    bus = RedisStreamEventBus(fake)  # type: ignore[arg-type]

    message_id = await bus.publish_raw(
        event_id="evt-1", event_type="ProjectCreated", payload='{"project_id": 1}'
    )

    ((stream, fields),) = fake.calls
    assert message_id == "1-0"
    assert stream == EVENTS_STREAM
    assert fields == {"type": "ProjectCreated", "payload": '{"project_id": 1}', "event_id": "evt-1"}


async def test_publish_raw_raises_on_connection_errors():
    """The relay must see the failure, so it leaves the row unpublished."""
    bus = RedisStreamEventBus(FakeRedis(fail=True))  # type: ignore[arg-type]

    with pytest.raises(redis.ConnectionError):
        await bus.publish_raw(event_id="evt-1", event_type="ProjectCreated", payload="{}")


# ── Consumer worker ───────────────────────────────────────────────────


class FakeAsyncRedis:
    """Scripted xreadgroup batches; raises CancelledError when the script ends.

    Every scripting hook defaults to the inert behaviour the original fake
    had, so tests that only care about batches stay a one-argument call:

      read_errors    exception raised by the Nth xreadgroup call (None = none)
      group_errors   exception raised by the Nth xgroup_create call
      pending        entries returned by xpending_range (reclaim scan input)
      pending_errors exception raised by the Nth xpending_range call
      entries        {message_id: fields}, the stream's contents as seen by
                     xclaim (redelivery) and xrange (dead-letter copy)
      xadd_errors    exception raised by the Nth xadd call (dead-letter write)

    `calls` is a single ordered trace of every command name, so a test can
    assert on call *order* (e.g. reclaim before the first read).
    """

    def __init__(
        self,
        batches: list[list[tuple[str, dict[str, str]]]],
        *,
        read_errors: list[BaseException | None] | None = None,
        group_errors: list[BaseException | None] | None = None,
        pending: list[dict[str, Any]] | None = None,
        pending_errors: list[BaseException | None] | None = None,
        entries: dict[str, dict[str, str]] | None = None,
        xadd_errors: list[BaseException | None] | None = None,
    ):
        self._batches = list(batches)
        self.acked: list[str] = []
        self.group_created = False
        self.calls: list[str] = []
        self.consumers: list[str] = []
        self.claimed: list[str] = []
        self._read_errors = list(read_errors or [])
        self._group_errors = list(group_errors or [])
        self._pending = list(pending or [])
        self._pending_errors = list(pending_errors or [])
        self._entries = dict(entries or {})
        self._xadd_errors = list(xadd_errors or [])
        self.added: list[tuple[str, dict[str, str]]] = []

    @staticmethod
    def _maybe_raise(scripted: list[BaseException | None]) -> None:
        if scripted:
            error = scripted.pop(0)
            if error is not None:
                raise error

    async def xgroup_create(self, stream, group, id, mkstream=False):
        self.calls.append("xgroup_create")
        self._maybe_raise(self._group_errors)
        self.group_created = True

    async def xreadgroup(self, group, consumer, streams, count, block=None):
        self.calls.append("xreadgroup")
        self.consumers.append(consumer)
        self._maybe_raise(self._read_errors)
        if not self._batches:
            raise asyncio.CancelledError
        return [(EVENTS_STREAM, self._batches.pop(0))]

    async def xack(self, stream, group, message_id):
        self.calls.append("xack")
        self.acked.append(message_id)

    async def xpending_range(self, stream, group, min=None, max=None, count=None, idle=None):
        self.calls.append("xpending_range")
        self._maybe_raise(self._pending_errors)
        return list(self._pending)

    async def xclaim(self, stream, group, consumer, min_idle_time, message_ids):
        self.calls.append("xclaim")
        claimed = []
        for message_id in message_ids:
            self.claimed.append(message_id)
            if message_id in self._entries:
                claimed.append((message_id, self._entries[message_id]))
        return claimed

    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        self.calls.append("xadd")
        self._maybe_raise(self._xadd_errors)
        self.added.append((stream, dict(fields)))
        return "9-0"

    async def xrange(self, stream, min=None, max=None, count=None):
        self.calls.append("xrange")
        fields = self._entries.get(min)
        return [(min, fields)] if fields is not None else []


@pytest.fixture
def recorded_sleeps(monkeypatch):
    """Replaces asyncio.sleep with a recorder that yields but never waits.

    The worker's backoff sleeps are 5 s of real time; the tests need the
    durations, not the delay. Restored by monkeypatch at teardown.
    """
    real_sleep = asyncio.sleep
    slept: list[float] = []

    async def fake_sleep(delay, *args, **kwargs):
        slept.append(delay)
        return await real_sleep(0)

    monkeypatch.setattr(worker_module.asyncio, "sleep", fake_sleep)
    return slept


async def _run_worker(fake: FakeAsyncRedis, handler, **kwargs) -> None:
    """The worker awaits its handler, so the plain recording callables the
    tests pass are wrapped in a coroutine function here."""

    async def _handler(ev, mid):
        handler(ev, mid)

    worker = EventWorker(fake, group="test", handler=_handler, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(asyncio.CancelledError):
        await worker.run()


async def test_worker_delivers_event_and_acks():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(batches=[[], [("1-0", serialize(event))]])
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert fake.group_created
    assert handled == [(event, "1-0")]
    assert fake.acked == ["1-0"]


async def test_worker_keeps_message_pending_when_handler_fails():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(batches=[[("1-0", serialize(event))]])

    def failing_handler(ev, mid):
        raise RuntimeError("boom")

    await _run_worker(fake, failing_handler)

    assert fake.acked == []  # unacked → redelivered by the reclaim scan


async def test_worker_drops_undecodable_message():
    fake = FakeAsyncRedis(batches=[[("1-0", {"type": "Nope", "payload": "{}"})]])
    handled: list[Any] = []

    await _run_worker(fake, lambda ev, mid: handled.append(ev))

    assert handled == []
    assert fake.acked == ["1-0"]  # acked so it can't poison the group forever


# ── Worker resilience ─────────────────────────────────────────────────
#
# No single unhandled exception may permanently kill a consumer group:
# run() supervises one session and restarts it after a backoff.


async def test_worker_survives_an_unexpected_error_from_the_read_path(recorded_sleeps):
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[[("1-0", serialize(event))]],
        read_errors=[TypeError("unexpected reply shape")],
    )
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert handled == [(event, "1-0")]  # the next message still gets delivered
    assert fake.acked == ["1-0"]


async def test_worker_survives_an_unexpected_error_from_the_reclaim_scan(
    monkeypatch, recorded_sleeps
):
    monkeypatch.setattr(worker_module, "_RECLAIM_INTERVAL_S", 0.0)
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[[("1-0", serialize(event))]],
        pending_errors=[KeyError("times_delivered")],
    )
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert len(handled) == 1
    assert fake.acked == ["1-0"]


async def test_worker_backs_off_before_retrying_after_an_unexpected_error(recorded_sleeps):
    """The backoff is load-bearing: a non-blocking read (read_id != ">")
    passes block=None, so a persistently raising read path would spin at
    100% CPU without it."""
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[[("1-0", serialize(event))]],
        read_errors=[TypeError("unexpected reply shape")],
    )

    await _run_worker(fake, lambda ev, mid: None)

    assert recorded_sleeps == [worker_module._ERROR_BACKOFF_S]
    assert fake.acked == ["1-0"]


async def test_worker_still_propagates_cancellation(recorded_sleeps):
    """The new `except Exception` arm must never swallow shutdown.
    CancelledError is a BaseException in 3.13, this pins that it stays one."""
    fake = FakeAsyncRedis(batches=[], read_errors=[asyncio.CancelledError()])

    await _run_worker(fake, lambda ev, mid: None)

    assert recorded_sleeps == []  # cancelled, not backed off


async def test_worker_recovers_when_group_creation_fails_once(recorded_sleeps):
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[[("1-0", serialize(event))]],
        group_errors=[redis.ResponseError("ERR transient")],
    )
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert fake.group_created  # the retry got the group created
    assert len(handled) == 1


async def test_worker_creates_a_group_redis_lost_again_without_backing_off(
    recorded_sleeps, glados_caplog
):
    """A Redis that comes back empty answers NOGROUP; the worker creates the
    group again at once instead of retrying the read forever."""
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[[("1-0", serialize(event))]],
        read_errors=[redis.ResponseError("NOGROUP No such key 'glados:events'")],
    )
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert fake.calls.count("xgroup_create") == 2  # at start and after the loss
    assert recorded_sleeps == []
    assert handled == [(event, "1-0")]
    assert any("consumer group is gone" in r.getMessage() for r in glados_caplog.records)


# ── Consumer identity ─────────────────────────────────────────────────


def test_consumer_name_is_unique_per_process(monkeypatch):
    pids = iter([111, 222])
    monkeypatch.setattr(worker_module.os, "getpid", lambda: next(pids))

    first = EventWorker(None, group="webhooks", handler=lambda ev, mid: None)  # type: ignore[arg-type]
    second = EventWorker(None, group="webhooks", handler=lambda ev, mid: None)  # type: ignore[arg-type]

    assert first._consumer != second._consumer
    assert first._consumer.startswith("webhooks-")
    assert second._consumer.startswith("webhooks-")


async def test_explicit_consumer_name_is_honoured():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(batches=[[("1-0", serialize(event))]])

    await _run_worker(fake, lambda ev, mid: None, consumer="fixed")

    assert set(fake.consumers) == {"fixed"}


async def test_worker_reclaims_orphans_before_its_first_read():
    """A crashed process's pending entries are registered under ITS consumer
    name, so this consumer's own read_id="0" pass finds nothing. Only the
    group-wide reclaim scan recovers them, so it has to run at startup."""
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fields = serialize(event)
    fake = FakeAsyncRedis(
        batches=[],
        pending=[
            {
                "message_id": "5-0",
                "consumer": "webhooks-deadhost-1",
                "time_since_delivered": 120_000,
                "times_delivered": 1,
            }
        ],
        entries={"5-0": fields},
    )
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert fake.calls.index("xpending_range") < fake.calls.index("xreadgroup")
    assert fake.claimed == ["5-0"]
    assert handled == [(event, "5-0")]
    assert fake.acked == ["5-0"]


# ── Redelivery backoff and terminal-failure logging ───────────────────


def _pending_entry(times_delivered: int, idle_ms: int, message_id: str = "5-0"):
    return {
        "message_id": message_id,
        "consumer": "test-other",
        "time_since_delivered": idle_ms,
        "times_delivered": times_delivered,
    }


async def test_reclaim_skips_an_entry_whose_backoff_has_not_elapsed():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    # Attempt 3 must wait 60s * 2**2 = 240s; only 100s have passed.
    fake = FakeAsyncRedis(
        batches=[],
        pending=[_pending_entry(times_delivered=3, idle_ms=100_000)],
        entries={"5-0": serialize(event)},
    )
    handled: list[Any] = []

    await _run_worker(fake, lambda ev, mid: handled.append(ev))

    assert fake.claimed == []
    assert handled == []
    assert fake.acked == []  # still pending, not dropped


async def test_reclaim_redelivers_once_the_backoff_has_elapsed():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[],
        pending=[_pending_entry(times_delivered=3, idle_ms=300_000)],
        entries={"5-0": serialize(event)},
    )
    handled: list[Any] = []

    await _run_worker(fake, lambda ev, mid: handled.append(ev))

    assert fake.claimed == ["5-0"]
    assert handled == [event]
    assert fake.acked == ["5-0"]


async def test_backoff_is_capped():
    """Without the cap, attempt 10 would demand 60s * 2**9 ~= 8.5 hours."""
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[],
        # times_delivered is below _MAX_DELIVERIES only because the drop
        # budget is checked first; use the cap value itself as the idle time.
        pending=[_pending_entry(times_delivered=4, idle_ms=worker_module._MAX_IDLE_MS)],
        entries={"5-0": serialize(event)},
    )
    handled: list[Any] = []

    await _run_worker(fake, lambda ev, mid: handled.append(ev))

    # 60s * 2**3 = 480s < the 900s cap, so this also pins that the cap is a
    # ceiling and not a floor: an entry above the cap is always redelivered.
    assert fake.claimed == ["5-0"]
    assert handled == [event]


async def test_message_is_dropped_and_logged_with_its_type_after_max_deliveries(glados_caplog):
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[],
        pending=[_pending_entry(times_delivered=5, idle_ms=999_999)],
        entries={"5-0": serialize(event)},
    )
    handled: list[Any] = []

    await _run_worker(fake, lambda ev, mid: handled.append(ev))

    assert handled == []  # budget exhausted, not retried
    assert fake.acked == ["5-0"]
    (record,) = [r for r in glados_caplog.records if r.levelno == logging.ERROR]
    message = record.getMessage()
    assert "'test'" in message  # the consumer group
    assert "5-0" in message
    assert "ProjectCreated" in message


async def test_dead_lettered_message_keeps_its_fields_and_is_acked_after_the_copy():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fields = serialize(event)
    fake = FakeAsyncRedis(
        batches=[],
        pending=[_pending_entry(times_delivered=5, idle_ms=999_999)],
        entries={"5-0": fields},
    )

    await _run_worker(fake, lambda ev, mid: None)

    ((stream, dead),) = fake.added
    assert stream == "glados:events:dead"
    assert dead["type"] == fields["type"] and dead["payload"] == fields["payload"]
    assert dead["dead_group"] == "test"
    assert dead["dead_source_id"] == "5-0"
    assert dead["dead_deliveries"] == "5"
    assert fake.calls.index("xadd") < fake.calls.index("xack")
    assert fake.acked == ["5-0"]


async def test_message_stays_pending_when_the_dead_letter_write_fails(glados_caplog):
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(
        batches=[],
        pending=[_pending_entry(times_delivered=5, idle_ms=999_999)],
        entries={"5-0": serialize(event)},
        xadd_errors=[redis.ConnectionError("down")],
    )

    await _run_worker(fake, lambda ev, mid: None)

    assert fake.acked == []  # retried by the next reclaim scan, never lost


# ── Producer-assigned event id ────────────────────────────────────────
#
# The outbox relay may re-publish a row after a crash between XADD and the
# published_at mark, producing a SECOND stream message for the same event.
# Consumers dedupe on the identity the worker hands them, so that identity
# must be the producer's, not the transport's.


def test_codec_round_trip_ignores_the_extra_event_id_field():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)

    fields = serialize(event, event_id="evt-1")

    assert fields["event_id"] == "evt-1"
    assert deserialize(fields) == event  # decode reads type/payload by name


def test_serialize_omits_the_event_id_field_when_none_is_given():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    assert set(serialize(event)) == {"type", "payload"}


async def test_worker_passes_the_stable_event_id_to_the_handler():
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(batches=[[("1-0", serialize(event, event_id="evt-42"))]])
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert handled == [(event, "evt-42")]  # not the Redis message id
    assert fake.acked == ["1-0"]  # acked by transport id, as always


async def test_worker_falls_back_to_the_message_id_when_event_id_is_absent():
    """Messages already in flight when the outbox was deployed carry no
    event_id; they must stay decodable and keep deduping under the identity
    they were originally processed with."""
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)
    fake = FakeAsyncRedis(batches=[[("1-0", serialize(event))]])
    handled: list[tuple[Any, str]] = []

    await _run_worker(fake, lambda ev, mid: handled.append((ev, mid)))

    assert handled == [(event, "1-0")]
