"""
Keeps the glados:events stream bounded without dropping work a consumer
group still owes.

Publishing does not trim with `XADD MAXLEN`, which removes the oldest
entries whether or not every group has processed them. A message that is
still pending in a slow or stalled group could vanish before its retry, and
its redelivery would then silently find nothing. Trimming happens here
instead: for each group the oldest entry it still needs is its oldest
pending message, or, with nothing pending, the last one it was delivered.
Everything older than the lowest of those across all groups is trimmed with
`XTRIM MINID`, which never touches an id at or above the floor.

A group whose worker never runs (a stale group left in Redis) would hold the
floor back forever, so a hard cap still applies far above normal operation.
Hitting it is logged as an error, because entries a group has not processed
are dropped at that point to protect Redis memory.

Every app worker runs this on an interval. XTRIM is idempotent and the floor
only moves forward (pending ids only get acked, delivered ids only grow), so
concurrent runs need no lock.
"""

import redis.asyncio

from src.modules.platform.infrastructure.events.registry import EVENTS_STREAM
from src.modules.platform.infrastructure.logging.logger import log

TRIM_INTERVAL_SECONDS = 60
HARD_CAP = 500_000


def _id_key(stream_id: str) -> tuple[int, int]:
    milliseconds, _, sequence = stream_id.partition("-")
    return int(milliseconds), int(sequence or 0)


async def _oldest_needed_id(client: redis.asyncio.Redis, stream: str) -> str | None:
    groups = await client.xinfo_groups(stream)
    floor: str | None = None
    for group in groups:
        summary = await client.xpending(stream, group["name"])
        needed = str(summary["min"]) if summary["pending"] else str(group["last-delivered-id"])
        if floor is None or _id_key(needed) < _id_key(floor):
            floor = needed
    return floor


async def trim_events_stream(client: redis.asyncio.Redis, stream: str = EVENTS_STREAM) -> int:
    """Trims entries every consumer group is done with, then enforces the
    hard cap. Returns how many entries were removed."""
    if not await client.exists(stream):
        return 0
    trimmed = 0
    floor = await _oldest_needed_id(client, stream)
    if floor is not None:
        trimmed += int(await client.xtrim(stream, minid=floor, approximate=True))

    length = int(await client.xlen(stream))
    if length > HARD_CAP:
        dropped = int(await client.xtrim(stream, maxlen=HARD_CAP, approximate=True))
        trimmed += dropped
        log.error(
            "Event stream %s held %d entries, over the hard cap of %d; dropped %d, "
            "including entries a consumer group had not processed. Check for a "
            "stalled or stale consumer group (XINFO GROUPS %s).",
            stream,
            length,
            HARD_CAP,
            dropped,
            stream,
        )
    return trimmed
