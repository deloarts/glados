"""
Puts relayed outbox rows on the events stream once more, run as
`admin republish-outbox`. It is the way back after Redis lost the events
stream: the outbox keeps every relayed row for 30 days, and a row put back
reaches every consumer group again as a new stream message with the same
producer-assigned event id.

The rows are read by the time the relay published them, from `since` up to
`until` when given, optionally limited to some event types, and appended to
the stream in id order. Consumers recognise an event they already handled
by that event id and skip it, which is what makes a generous `since`
cheap; docs/reference/operations-recovery.md section 6.1 names the few
effects that do repeat.
The appended messages land behind every newer event already on the stream,
which consumers accept, since they never rely on the order of events.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.modules.platform.ports.outbound.event_outbox_port import OutboxMessage

BATCH_SIZE = 500


async def republish(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    publish: Callable[[OutboxMessage], Awaitable[None]] | None,
    since: datetime,
    until: datetime | None,
    event_types: Sequence[str],
    counts: Counter[str],
    batch_size: int = BATCH_SIZE,
) -> None:
    """Publishes every matching row through `publish`, or only counts them
    when `publish` is None (a dry run), adding each to `counts` by event
    type. A failing publish raises with `counts` holding what went out
    before it, and running the command again with the same bounds finishes
    the work."""
    from src.modules.platform.adapters.outbound.persistence.event_outbox import (
        SqlAlchemyEventOutbox,
    )

    after_id = 0
    while True:
        async with session_factory() as db:
            messages = await SqlAlchemyEventOutbox(db).fetch_published(
                since=since,
                until=until,
                event_types=event_types,
                after_id=after_id,
                limit=batch_size,
            )
        if not messages:
            return
        for message in messages:
            if publish is not None:
                await publish(message)
            counts[message.event_type] += 1
        after_id = messages[-1].id
