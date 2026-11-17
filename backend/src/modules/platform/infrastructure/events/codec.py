"""
Serializes domain events to Redis Stream fields and back.

Redis Streams store flat string maps, so each event travels as two fields:
    type   - the event class name (dispatch key into EVENT_REGISTRY)
    payload, all event fields as one JSON document

plus an optional third:
    event_id, the producer-assigned identity used by consumers for
              idempotency. Set by the transactional outbox, which may
              re-publish a row after a crash between XADD and marking it
              published: the Redis message id differs on the second attempt,
              this one does not. Optional and read by name, so a message
              published without one still decodes.

JSON keeps int/bool/str intact across the round trip; enums are stored by
`.value`, dates as ISO strings. Deserialization rebuilds the typed dataclass
by coercing each JSON value against the dataclass's type hints.
"""

import dataclasses
import json
import types
import typing
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from enum import Enum
from typing import Any

from src.modules.platform.infrastructure.events.registry import EVENT_REGISTRY
from src.shared_kernel.domain.events.base import DomainEvent

EVENT_ID_FIELD = "event_id"


class EventCodecError(Exception):
    """A message cannot be encoded or decoded. Consumers drop such messages."""


def serialize(event: DomainEvent, event_id: str | None = None) -> dict[str, str]:
    """`event_id` is optional; when given it rides along as a third stream
    field (see the module docstring)."""
    event_cls = type(event)
    name = event_cls.__name__
    if EVENT_REGISTRY.get(name) is not event_cls:
        raise EventCodecError(f"Event type {name!r} is not registered in EVENT_REGISTRY.")
    payload = json.dumps(dataclasses.asdict(event), default=_encode_special)
    fields = {"type": name, "payload": payload}
    if event_id is not None:
        fields[EVENT_ID_FIELD] = event_id
    return fields


def deserialize(fields: Mapping[str, str]) -> DomainEvent:
    try:
        name = fields["type"]
        payload = fields["payload"]
    except KeyError as e:
        raise EventCodecError(f"Stream message is missing the {e} field.") from e

    cls = EVENT_REGISTRY.get(name)
    if cls is None:
        raise EventCodecError(f"Unknown event type {name!r}.")

    try:
        data = json.loads(payload)
        hints = typing.get_type_hints(cls)
        kwargs = {key: _decode_value(hints[key], value) for key, value in data.items()}
        return cls(**kwargs)
    except Exception as e:
        raise EventCodecError(f"Cannot decode {name!r} payload: {e}") from e


def _encode_special(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date | datetime):
        return obj.isoformat()
    raise TypeError(f"{type(obj).__name__} is not JSON-serializable.")


def _decode_value(hint: Any, value: Any) -> Any:
    if value is None:
        return None

    origin = typing.get_origin(hint)
    if origin is types.UnionType or origin is typing.Union:
        # Events only use `X | None`; decode against the non-None member.
        non_none = [a for a in typing.get_args(hint) if a is not type(None)]
        return _decode_value(non_none[0], value)
    if origin is list:
        (item_hint,) = typing.get_args(hint)
        return [_decode_value(item_hint, item) for item in value]

    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return hint(value)
        if hint is datetime:
            return datetime.fromisoformat(value)
        if hint is date:
            return date.fromisoformat(value)

    return value
