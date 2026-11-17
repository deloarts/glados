"""
Per-file lock that keeps two ingests of the same PDM file from running at
once: the poller's parallel workers, the add-in trigger worker and an
admin retry can all reach the same file. The second caller waits until the
first is done, then finds the file already in sync.
"""

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class IPdmFileLock(Protocol):
    def hold(self, file_id: int) -> AbstractAsyncContextManager[None]:
        """Waits for and holds the lock for `file_id` until the `with` block
        exits. A no-op on a non-Postgres database (SQLite, used by the
        tests), which is single-process anyway."""
        ...
