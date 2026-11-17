"""Live row-sync change capture: listens on the sync Session class behind the
shared SessionLocal factory, maps every flushed ORM object to its live-sync
topic, and publishes one batched signal per commit to Redis Pub/Sub
(channel `glados:live`).

The after_commit listener runs synchronously inside the AsyncSession's
commit, so it cannot await the publish. It hands the publish to the running
event loop as a task instead and keeps a reference to it until it finishes.
A commit outside any event loop (a plain sync Session) has nowhere to run
that task, and its signals are dropped.

It is deliberately not driven by domain events: most writes publish none,
while session-level capture sees every commit, cascades included.

The signal carries row identity only (resource, id, action, actor), never
row data, so permissions stay enforced by the normal authenticated REST
path the client uses to refetch the row.
"""

import asyncio
import json
from dataclasses import asdict
from dataclasses import dataclass

import redis
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.infrastructure.events.registry import LIVE_CHANNEL
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.ports.outbound.live_signal import LiveAction
from src.modules.platform.ports.outbound.live_signal import LiveSignal

# Beyond this many rows of one resource, a commit sends one "bulk" signal.
_BULK_THRESHOLD = 50

_INFO_KEY = "live_changes"  # session.info bucket, accumulated across flushes in one transaction

# Merge priority for one row recorded several times in a transaction:
# deleted wins, and created beats updated, since a client that never saw
# the row needs the full refresh.
_ACTION_PRIORITY: dict[LiveAction, int] = {"updated": 0, "created": 1, "bulk": 2, "deleted": 3}

# Strong references to in-flight publish tasks; the event loop only keeps a
# weak one, so an unreferenced task could be garbage collected mid-publish.
_publish_tasks: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class LiveTopic:
    """Where a changed row of a model is signalled: the live resource and
    the id within it."""

    resource: str
    # "id", a parent FK column, or a dotted path for a row two hops away.
    id_attr: str
    # The row is nested in the referenced one, so its changes always count
    # as "updated"; deleting an order item must not delete the order.
    child: bool = False


def _resolve_id(obj: Base, id_attr: str) -> int | None:
    value: object = obj
    for part in id_attr.split("."):
        if value is None:
            return None
        value = getattr(value, part, None)
    return value if isinstance(value, int) else None


# The live-sync topics per model; a model shown nested in several tables
# has several. Unlisted models, such as logs and usage records, stay quiet.
# Each module registers its models at startup through
# src/bootstrap/registrations.py.
MODEL_TOPICS: dict[type[Base], tuple[LiveTopic, ...]] = {}


def register_live_topics(topics: dict[type[Base], tuple[LiveTopic, ...]]) -> None:
    """Adds the live-sync topics of models whose changes clients follow."""
    MODEL_TOPICS.update(topics)


def _record(session: Session, obj: Base, action: LiveAction) -> None:
    topics = MODEL_TOPICS.get(type(obj))
    if topics is None:
        return
    changes: dict[tuple[str, int], LiveAction] = session.info.setdefault(_INFO_KEY, {})
    for topic in topics:
        row_id = _resolve_id(obj, topic.id_attr)
        if row_id is None:
            continue
        recorded_action: LiveAction = "updated" if topic.child else action
        key = (topic.resource, row_id)
        existing = changes.get(key)
        if existing is None or _ACTION_PRIORITY[recorded_action] > _ACTION_PRIORITY[existing]:
            changes[key] = recorded_action


def record_update(session: Session, obj: Base) -> None:
    """Records an update written without the unit of work's flush, such as a
    Core executemany, so live sync still signals the row."""
    _record(session, obj, "updated")


def _after_flush(session: Session, _flush_context: object) -> None:
    # At after_flush the collections still hold the flushed objects with
    # their new PKs; by after_flush_postexec they are already empty.
    for obj in session.new:
        _record(session, obj, "created")
    for obj in session.dirty:
        if session.is_modified(obj, include_collections=False):
            _record(session, obj, "updated")
    for obj in session.deleted:
        _record(session, obj, "deleted")


def _after_commit(session: Session) -> None:
    changes: dict[tuple[str, int], LiveAction] | None = session.info.pop(_INFO_KEY, None)
    if changes:
        _publish(changes)


def _discard_buffer(session: Session, *_args: object) -> None:
    session.info.pop(_INFO_KEY, None)


def _publish(changes: dict[tuple[str, int], LiveAction]) -> None:
    actor_id = user_id_var.get()
    by_resource: dict[str, list[tuple[int, LiveAction]]] = {}
    for (resource, row_id), action in changes.items():
        by_resource.setdefault(resource, []).append((row_id, action))

    signals: list[LiveSignal] = []
    for resource, rows in by_resource.items():
        if len(rows) > _BULK_THRESHOLD:
            signals.append(LiveSignal(resource=resource, id=0, action="bulk", actor_id=actor_id))
        else:
            signals.extend(
                LiveSignal(resource=resource, id=row_id, action=action, actor_id=actor_id)
                for row_id, action in rows
            )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log.debug("Live sync: no running event loop; dropping %d signal(s).", len(signals))
        return
    task = loop.create_task(_send(json.dumps([asdict(s) for s in signals]), len(signals)))
    _publish_tasks.add(task)
    task.add_done_callback(_publish_tasks.discard)


async def _send(message: str, count: int) -> None:
    # Best effort: a lost signal heals on the client's next refresh.
    try:
        await get_async_redis_client().publish(LIVE_CHANNEL, message)
    except redis.RedisError:
        log.warning("Live sync: failed to publish %d signal(s); dropping.", count)


def register_change_tracking(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Attaches the listeners to the sync Session class behind the factory,
    where ORM session events live. Call once at startup."""
    sync_cls: type[Session] = session_factory.class_.sync_session_class
    for name, fn in (
        ("after_flush", _after_flush),
        ("after_commit", _after_commit),
        ("after_rollback", _discard_buffer),
        ("after_soft_rollback", _discard_buffer),
    ):
        if not event.contains(sync_cls, name, fn):
            event.listen(sync_cls, name, fn)
