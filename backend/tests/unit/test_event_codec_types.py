"""
Covers the field types codec.py's `_decode_value` supports but that no
*currently registered* event actually uses yet: date, datetime, list[...],
optional (`X | None`), and enums nested inside a list.

test_event_bus.py already round-trips every registered event, but today
every one of them is built only from int/str/bool/float/enum fields, so
the date/datetime/list branches (codec.py:79-88) were entirely dead in
the test suite despite being live, reachable code. The moment someone adds
a `date` field to a real event, these paths run in production; a silent
break there would surface as undecodable messages that consumers drop.

These tests register throwaway event classes in EVENT_REGISTRY for the
duration of one test, then restore it, exercising the real public
serialize/deserialize API rather than poking at the private helper.

The PdmFileChangeRequested.source section at the bottom is the one
exception: it round-trips the real, already-registered event.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.platform.infrastructure.events.codec import EventCodecError
from src.modules.platform.infrastructure.events.codec import deserialize
from src.modules.platform.infrastructure.events.codec import serialize
from src.modules.platform.infrastructure.events.registry import EVENT_REGISTRY


@pytest.fixture
def register_event() -> Iterator[object]:
    """Temporarily adds event classes to EVENT_REGISTRY, restoring the
    original mapping afterwards so no test leaks into another."""
    added: list[str] = []

    def _register(cls: type) -> type:
        EVENT_REGISTRY[cls.__name__] = cls
        added.append(cls.__name__)
        return cls

    yield _register

    for name in added:
        EVENT_REGISTRY.pop(name, None)


# ── date / datetime ───────────────────────────────────────────────────


def test_round_trip_rebuilds_a_date_field(register_event):
    @dataclass(frozen=True)
    class _DateEvent:
        when: date

    register_event(_DateEvent)

    restored = deserialize(serialize(_DateEvent(when=date(2026, 8, 3))))

    assert restored.when == date(2026, 8, 3)
    assert isinstance(restored.when, date)


def test_round_trip_rebuilds_a_datetime_field(register_event):
    @dataclass(frozen=True)
    class _DateTimeEvent:
        when: datetime

    register_event(_DateTimeEvent)
    original = datetime(2026, 8, 3, 14, 30, tzinfo=UTC)

    restored = deserialize(serialize(_DateTimeEvent(when=original)))

    assert restored.when == original
    assert isinstance(restored.when, datetime)
    assert restored.when.tzinfo is not None


def test_datetime_is_not_silently_downgraded_to_date(register_event):
    """date and datetime are separate branches, a decoder that hit the
    `date` branch first would truncate the time component."""

    @dataclass(frozen=True)
    class _DateTimePrecisionEvent:
        when: datetime

    register_event(_DateTimePrecisionEvent)
    original = datetime(2026, 8, 3, 14, 30, 15, tzinfo=UTC)

    restored = deserialize(serialize(_DateTimePrecisionEvent(when=original)))

    assert restored.when.hour == 14
    assert restored.when.minute == 30
    assert restored.when.second == 15


# ── list[...] ─────────────────────────────────────────────────────────


def test_round_trip_rebuilds_a_list_of_ints(register_event):
    @dataclass(frozen=True)
    class _IntListEvent:
        ids: list[int]

    register_event(_IntListEvent)

    restored = deserialize(serialize(_IntListEvent(ids=[1, 2, 3])))

    assert restored.ids == [1, 2, 3]


def test_round_trip_rebuilds_an_empty_list(register_event):
    @dataclass(frozen=True)
    class _EmptyListEvent:
        ids: list[int]

    register_event(_EmptyListEvent)

    assert deserialize(serialize(_EmptyListEvent(ids=[]))).ids == []


def test_round_trip_rebuilds_enum_members_inside_a_list(register_event):
    """The list branch recurses per item, so enum coercion must survive
    nesting, plain `==` can't catch this since str-enums compare equal
    to their raw value."""

    @dataclass(frozen=True)
    class _EnumListEvent:
        statuses: list[BoughtItemCatalogueStatus]

    register_event(_EnumListEvent)
    event = _EnumListEvent(
        statuses=[BoughtItemCatalogueStatus.ACTIVE, BoughtItemCatalogueStatus.REPLACED]
    )

    restored = deserialize(serialize(event))

    assert all(isinstance(s, BoughtItemCatalogueStatus) for s in restored.statuses)
    assert restored.statuses == event.statuses


def test_round_trip_rebuilds_a_list_of_dates(register_event):
    @dataclass(frozen=True)
    class _DateListEvent:
        days: list[date]

    register_event(_DateListEvent)
    event = _DateListEvent(days=[date(2026, 1, 1), date(2026, 8, 3)])

    restored = deserialize(serialize(event))

    assert restored.days == event.days
    assert all(isinstance(d, date) for d in restored.days)


# ── optional (X | None) ───────────────────────────────────────────────


def test_round_trip_preserves_a_populated_optional(register_event):
    @dataclass(frozen=True)
    class _OptionalDateEvent:
        when: date | None

    register_event(_OptionalDateEvent)

    restored = deserialize(serialize(_OptionalDateEvent(when=date(2026, 8, 3))))

    assert restored.when == date(2026, 8, 3)
    assert isinstance(restored.when, date)


def test_round_trip_preserves_a_none_optional(register_event):
    @dataclass(frozen=True)
    class _OptionalDateNoneEvent:
        when: date | None

    register_event(_OptionalDateNoneEvent)

    assert deserialize(serialize(_OptionalDateNoneEvent(when=None))).when is None


def test_round_trip_preserves_an_optional_enum(register_event):
    @dataclass(frozen=True)
    class _OptionalEnumEvent:
        status: BoughtItemCatalogueStatus | None

    register_event(_OptionalEnumEvent)
    event = _OptionalEnumEvent(status=BoughtItemCatalogueStatus.ACTIVE)

    restored = deserialize(serialize(event))

    assert isinstance(restored.status, BoughtItemCatalogueStatus)


# ── encoder rejection ─────────────────────────────────────────────────


def test_serialize_rejects_a_field_type_it_cannot_encode(register_event):
    """_encode_special raises TypeError for unknown types; json.dumps
    surfaces it rather than writing a corrupt payload."""

    class _NotSerializable:
        pass

    @dataclass(frozen=True)
    class _BadFieldEvent:
        thing: object

    register_event(_BadFieldEvent)

    with pytest.raises(TypeError):
        serialize(_BadFieldEvent(thing=_NotSerializable()))


def test_deserialize_rejects_an_out_of_range_enum_value(register_event):
    @dataclass(frozen=True)
    class _EnumEvent:
        status: BoughtItemCatalogueStatus

    register_event(_EnumEvent)

    with pytest.raises(EventCodecError):
        deserialize({"type": "_EnumEvent", "payload": '{"status": "not-a-real-status"}'})


def test_deserialize_rejects_an_unparseable_date(register_event):
    @dataclass(frozen=True)
    class _BadDateEvent:
        when: date

    register_event(_BadDateEvent)

    with pytest.raises(EventCodecError):
        deserialize({"type": "_BadDateEvent", "payload": '{"when": "not-a-date"}'})


# ── PdmFileChangeRequested.source ──────────────────────────────────────


def test_pdm_file_change_requested_round_trips_its_source_field():
    event = PdmFileChangeRequested(
        vault_name="MyVault",
        file_id=42,
        path=None,
        version=None,
        requested_by_id=7,
        source="retry",
        requested_by_name="Mira Holt",
    )

    restored = deserialize(serialize(event))

    assert restored.source == "retry"
