"""
Turns a blocking chunk reader from a storage SDK or file handle into an
async iterator, one worker-thread hop per chunk, so streaming a large object
never blocks the event loop and never holds more than one chunk in memory.
"""

from collections.abc import AsyncIterator
from collections.abc import Callable

from anyio import to_thread

CHUNK_SIZE = 1024 * 1024


async def iterate_in_thread(
    read_chunk: Callable[[], bytes], close: Callable[[], None]
) -> AsyncIterator[bytes]:
    """Yields `read_chunk()` results until one comes back empty, then calls
    `close`, which also runs when the consumer stops early."""
    try:
        while chunk := await to_thread.run_sync(read_chunk):
            yield chunk
    finally:
        await to_thread.run_sync(close)
