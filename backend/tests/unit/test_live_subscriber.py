"""
Unit tests for the live-sync Pub/Sub subscriber
(src/modules/platform/infrastructure/events/live_subscriber.py). No Redis server, the
client is replaced with in-memory fakes, mirroring tests/unit/test_event_bus.py's
FakeAsyncRedis for the Streams consumer worker.
"""

import asyncio
import json

import pytest

from src.modules.platform.infrastructure.events.live_subscriber import LiveEventSubscriber
from src.modules.platform.ports.outbound.live_signal import LiveSignal


class FakePubSub:
    """Scripted get_message() results; raises CancelledError once exhausted
    so the subscriber's infinite loop terminates for the test."""

    def __init__(self, messages: list[dict | None]):
        self._messages = list(messages)
        self.subscribed_channel: str | None = None

    async def __aenter__(self) -> "FakePubSub":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def subscribe(self, channel: str) -> None:
        self.subscribed_channel = channel

    # Mirrors redis.asyncio PubSub.get_message, whose signature has a timeout.
    async def get_message(
        self,
        ignore_subscribe_messages: bool = True,
        timeout: float = 0.0,  # noqa: ASYNC109
    ):
        if not self._messages:
            raise asyncio.CancelledError
        return self._messages.pop(0)


class FakeAsyncRedis:
    def __init__(self, messages: list[dict | None]):
        self._messages = messages
        self.pubsubs: list[FakePubSub] = []

    def pubsub(self, **_kwargs: object) -> FakePubSub:
        instance = FakePubSub(self._messages)
        self.pubsubs.append(instance)
        return instance


def _payload(*signals: LiveSignal) -> str:
    from dataclasses import asdict

    return json.dumps([asdict(s) for s in signals])


async def _run_subscriber(fake: FakeAsyncRedis, handler) -> None:
    subscriber = LiveEventSubscriber(fake, handler=handler)  # type: ignore[arg-type]
    with pytest.raises(asyncio.CancelledError):
        await subscriber.run()


async def test_subscriber_delivers_decoded_signals_to_handler():
    signal = LiveSignal(resource="orders", id=1, action="updated", actor_id=7)
    fake = FakeAsyncRedis(messages=[None, {"data": _payload(signal)}])
    received: list[list[LiveSignal]] = []

    await _run_subscriber(fake, lambda signals: received.append(signals))

    assert received == [[signal]]


async def test_subscriber_subscribes_to_the_configured_channel():
    fake = FakeAsyncRedis(messages=[])
    subscriber = LiveEventSubscriber(fake, handler=lambda signals: None, channel="glados:live")  # type: ignore[arg-type]

    with pytest.raises(asyncio.CancelledError):
        await subscriber.run()

    assert fake.pubsubs[0].subscribed_channel == "glados:live"


async def test_subscriber_drops_undecodable_message_without_dying():
    fake = FakeAsyncRedis(messages=[{"data": "not json"}, {"data": "[1, 2]"}])
    received: list[object] = []

    await _run_subscriber(fake, lambda signals: received.append(signals))

    assert received == []  # both malformed messages dropped, loop kept going


async def test_subscriber_survives_a_raising_handler():
    signal = LiveSignal(resource="orders", id=1, action="updated", actor_id=None)
    fake = FakeAsyncRedis(messages=[{"data": _payload(signal)}])

    def failing_handler(_signals: list[LiveSignal]) -> None:
        raise RuntimeError("boom")

    await _run_subscriber(fake, failing_handler)  # must not propagate RuntimeError
