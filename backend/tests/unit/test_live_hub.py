"""
Unit tests for the per-process live-sync connection registry
(src/modules/platform/adapters/inbound/api/live/hub.py). Pure asyncio, no Redis, no HTTP.
"""

from src.modules.platform.adapters.inbound.api.live import hub as hub_module
from src.modules.platform.adapters.inbound.api.live.hub import LiveHub
from src.modules.platform.adapters.inbound.api.live.hub import get_live_hub
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.live_signal import LiveSignal

_SIGNAL = LiveSignal(resource="orders", id=1, action="updated", actor_id=None)


# ── Per-connection permission filtering ─────────────────────────────────
#
# _RESOURCE_READ_PERMISSION maps every currently-emittable resource to
# None (open) today, see hub.py's module docstring, so these tests
# monkeypatch a resource to require a permission for the duration of the
# test in order to exercise the filtering mechanism itself.


def test_connection_without_the_required_permission_does_not_receive_the_signal(monkeypatch):
    monkeypatch.setitem(hub_module._RESOURCE_READ_PERMISSION, "orders", Permission.WRITE_ORDERS)
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1, permissions=frozenset())

    live_hub.broadcast([_SIGNAL])

    assert connection.queue.empty()


def test_connection_with_the_required_permission_receives_the_signal(monkeypatch):
    monkeypatch.setitem(hub_module._RESOURCE_READ_PERMISSION, "orders", Permission.WRITE_ORDERS)
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1, permissions=frozenset({Permission.WRITE_ORDERS}))

    live_hub.broadcast([_SIGNAL])

    assert connection.queue.get_nowait() == [_SIGNAL]


def test_write_settings_holder_receives_a_gated_signal_regardless_of_resource_permission(
    monkeypatch,
):
    monkeypatch.setitem(hub_module._RESOURCE_READ_PERMISSION, "orders", Permission.WRITE_ORDERS)
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1, permissions=frozenset({Permission.WRITE_SETTINGS}))

    live_hub.broadcast([_SIGNAL])

    assert connection.queue.get_nowait() == [_SIGNAL]


def test_systemuser_receives_a_gated_signal_regardless_of_resource_permission(monkeypatch):
    monkeypatch.setitem(hub_module._RESOURCE_READ_PERMISSION, "orders", Permission.WRITE_ORDERS)
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1, permissions=frozenset(), is_systemuser=True)

    live_hub.broadcast([_SIGNAL])

    assert connection.queue.get_nowait() == [_SIGNAL]


def test_unknown_resource_type_fails_open_and_is_delivered():
    """A resource with no entry at all in _RESOURCE_READ_PERMISSION (not
    even an explicit None) is more likely a mapping gap than something to
    hide, so it is delivered rather than dropped."""
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1, permissions=frozenset())
    signal = LiveSignal(resource="not-a-real-resource", id=1, action="updated", actor_id=None)

    live_hub.broadcast([signal])

    assert connection.queue.get_nowait() == [signal]


def test_broadcast_filters_independently_per_connection(monkeypatch):
    monkeypatch.setitem(hub_module._RESOURCE_READ_PERMISSION, "orders", Permission.WRITE_ORDERS)
    live_hub = LiveHub()
    allowed = live_hub.connect(user_id=1, permissions=frozenset({Permission.WRITE_ORDERS}))
    denied = live_hub.connect(user_id=2, permissions=frozenset())

    live_hub.broadcast([_SIGNAL])

    assert allowed.queue.get_nowait() == [_SIGNAL]
    assert denied.queue.empty()


def test_broadcast_drops_only_the_gated_signal_from_a_mixed_batch(monkeypatch):
    monkeypatch.setitem(hub_module._RESOURCE_READ_PERMISSION, "orders", Permission.WRITE_ORDERS)
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1, permissions=frozenset())
    open_signal = LiveSignal(resource="production-lots", id=1, action="updated", actor_id=None)

    live_hub.broadcast([_SIGNAL, open_signal])

    assert connection.queue.get_nowait() == [open_signal]


def test_every_emittable_resource_type_has_an_explicit_permission_mapping():
    """Enumerates every resource the live-sync subscriber can actually
    receive a signal for today: every LiveResource value used as a topic
    in change_tracking.MODEL_TOPICS, plus AUTO_PLAN_RUN, the one resource
    production_schedule.py constructs a LiveSignal for directly rather
    than through change tracking. A resource missing here would still
    fail open (see hub.py's module docstring), this test exists so that
    is a conscious choice, not a silent gap."""
    from src.modules.platform.adapters.outbound.persistence.change_tracking import MODEL_TOPICS
    from src.modules.platform.ports.outbound.live_signal import LiveResource

    emittable = {topic.resource for topics in MODEL_TOPICS.values() for topic in topics}
    emittable.add(LiveResource.AUTO_PLAN_RUN)

    assert emittable <= hub_module._RESOURCE_READ_PERMISSION.keys()


def test_broadcast_reaches_every_connection_across_users():
    live_hub = LiveHub()
    a = live_hub.connect(user_id=1)
    b = live_hub.connect(user_id=2)

    live_hub.broadcast([_SIGNAL])

    assert a.queue.get_nowait() == [_SIGNAL]
    assert b.queue.get_nowait() == [_SIGNAL]


def test_broadcast_of_empty_list_is_a_no_op():
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1)

    live_hub.broadcast([])

    assert connection.queue.empty()


def test_full_queue_flags_overflowed_instead_of_raising():
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1)
    for _ in range(hub_module._QUEUE_MAXSIZE):
        connection.queue.put_nowait([_SIGNAL])

    live_hub.broadcast([_SIGNAL])  # must not raise despite the full queue

    assert connection.overflowed is True


def test_sixth_connection_for_one_user_evicts_the_oldest():
    live_hub = LiveHub()
    connections = [live_hub.connect(user_id=1) for _ in range(hub_module._MAX_CONNECTIONS_PER_USER)]
    oldest = connections[0]

    newest = live_hub.connect(user_id=1)

    assert oldest.queue.get_nowait() is None  # evicted
    assert live_hub.connection_count == hub_module._MAX_CONNECTIONS_PER_USER
    assert newest.queue.empty()


def test_disconnect_removes_the_connection():
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1)

    live_hub.disconnect(connection)

    assert live_hub.connection_count == 0
    live_hub.broadcast([_SIGNAL])  # no connections left to raise on


def test_disconnect_is_idempotent():
    live_hub = LiveHub()
    connection = live_hub.connect(user_id=1)

    live_hub.disconnect(connection)
    live_hub.disconnect(connection)  # must not raise

    assert live_hub.connection_count == 0


def test_close_all_stops_every_connection():
    live_hub = LiveHub()
    a = live_hub.connect(user_id=1)
    b = live_hub.connect(user_id=2)

    live_hub.close_all()

    assert a.queue.get_nowait() is None
    assert b.queue.get_nowait() is None
    assert live_hub.connection_count == 0


def test_connection_count_reflects_all_users():
    live_hub = LiveHub()
    live_hub.connect(user_id=1)
    live_hub.connect(user_id=1)
    live_hub.connect(user_id=2)

    assert live_hub.connection_count == 3


def test_get_live_hub_is_a_process_wide_singleton():
    get_live_hub.cache_clear()
    try:
        assert get_live_hub() is get_live_hub()
    finally:
        get_live_hub.cache_clear()
