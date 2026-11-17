"""
What lifecycle_effects publishes for the lot and position changes the
reconciler writes: a lot status change publishes LotStatusChanged, a lot
that becomes COMPLETED publishes LotCompleted besides, a position status
change publishes LotPositionStatusChanged, and the lot timeline gets a row
unless the intent behind the change writes its own. Kind and count changes
publish nothing.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.services.lifecycle_effects import lifecycle_effects
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

ACTOR = actor()
_A = LifecycleAggregate


def _change(
    aggregate: LifecycleAggregate,
    row_id: int,
    old: str,
    new: str,
    field: LifecycleField = LifecycleField.STATUS,
) -> FieldChange:
    return FieldChange(
        aggregate=aggregate, id=row_id, field=field, old=old, new=new, rule="test", value=new
    )


def _lot_effects(world: FakeWorld, lot_id: int, old: LotStatus, new: LotStatus):
    return lifecycle_effects(
        [_change(_A.LOTS, lot_id, old.value, new.value)], world.snapshot(), ACTOR
    )


def test_a_lot_status_change_publishes_lot_status_changed_and_a_timeline_row() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.PLANNED)

    effects = _lot_effects(world, lot.id, LotStatus.PLANNED, LotStatus.IN_PROGRESS)

    [event] = effects.events
    assert isinstance(event, LotStatusChanged)
    assert (event.lot_id, event.old_status, event.new_status, event.actor_id) == (
        lot.id,
        LotStatus.PLANNED,
        LotStatus.IN_PROGRESS,
        ACTOR.id,
    )
    [row] = effects.lot_events
    assert (row.event_type, row.entity, row.summary) == (
        LotEventType.LOT_STATUS_CHANGED,
        "lot",
        "Status: planned → in_progress.",
    )
    assert row.payload == {"old_status": "planned", "new_status": "in_progress"}


def test_a_lot_the_facts_complete_publishes_lot_completed_once_with_its_own_row() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.IN_PROGRESS)

    effects = _lot_effects(world, lot.id, LotStatus.IN_PROGRESS, LotStatus.COMPLETED)

    assert [type(e) for e in effects.events] == [LotStatusChanged, LotCompleted]
    assert [(r.event_type, r.summary) for r in effects.lot_events] == [
        (LotEventType.LOT_COMPLETED, "Lot completed.")
    ]


def test_a_force_completed_lot_leaves_the_timeline_row_to_its_use_case() -> None:
    world = FakeWorld()
    lot = world.lot(
        status=LotStatus.IN_PROGRESS, force_completed_at=datetime(2026, 1, 2, tzinfo=UTC)
    )

    effects = _lot_effects(world, lot.id, LotStatus.IN_PROGRESS, LotStatus.COMPLETED)

    assert [type(e) for e in effects.events] == [LotStatusChanged, LotCompleted]
    assert effects.lot_events == ()


def test_a_scrapped_lot_gets_its_own_timeline_row() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.IN_PROGRESS, quantity=0.0)

    effects = _lot_effects(world, lot.id, LotStatus.IN_PROGRESS, LotStatus.SCRAPPED)

    assert [type(e) for e in effects.events] == [LotStatusChanged]
    assert [(r.event_type, r.summary) for r in effects.lot_events] == [
        (LotEventType.LOT_SCRAPPED, "Lot scrapped, nothing left to produce.")
    ]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (LotStatus.IN_PROGRESS, LotStatus.CANCELED),
        (LotStatus.IN_PROGRESS, LotStatus.ON_HOLD),
        (LotStatus.ON_HOLD, LotStatus.IN_PROGRESS),
        (LotStatus.ON_HOLD, LotStatus.DRAFT),
    ],
)
def test_cancel_hold_and_resume_leave_the_timeline_row_to_their_use_cases(
    old: LotStatus, new: LotStatus
) -> None:
    world = FakeWorld()
    lot = world.lot(status=old)

    effects = _lot_effects(world, lot.id, old, new)

    assert [type(e) for e in effects.events] == [LotStatusChanged]
    assert effects.lot_events == ()


def test_a_lot_leaving_hold_for_a_terminal_status_gets_its_row() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.ON_HOLD, quantity=0.0)

    effects = _lot_effects(world, lot.id, LotStatus.ON_HOLD, LotStatus.SCRAPPED)

    assert [r.event_type for r in effects.lot_events] == [LotEventType.LOT_SCRAPPED]


def test_a_position_status_change_publishes_lot_position_status_changed() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot, status=LotPositionStatus.ORDERED_OR_QUEUED)

    effects = lifecycle_effects(
        [_change(_A.LOT_POSITIONS, position.id, "ordered_or_queued", "in_progress")],
        world.snapshot(),
        ACTOR,
    )

    [event] = effects.events
    assert isinstance(event, LotPositionStatusChanged)
    assert (event.lot_id, event.position_id, event.old_status, event.new_status) == (
        lot.id,
        position.id,
        LotPositionStatus.ORDERED_OR_QUEUED,
        LotPositionStatus.IN_PROGRESS,
    )
    assert effects.lot_events == ()


def test_kind_and_count_changes_publish_nothing() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(lot)

    effects = lifecycle_effects(
        [
            _change(_A.LOT_POSITIONS, position.id, "unassigned", "internal", LifecycleField.KIND),
            _change(_A.LOT_POSITIONS, position.id, "0", "4", LifecycleField.QUANTITY_COMPLETED),
            _change(_A.LOTS, lot.id, "-", "set", LifecycleField.COMPLETED_AT),
        ],
        world.snapshot(),
        ACTOR,
    )

    assert (effects.events, effects.lot_events) == ((), ())
