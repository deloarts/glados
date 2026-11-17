"""
Advisory lock guarding one PDM poll tick, so only one of the worker
processes runs PollPdmVault when its interval is due. It uses the same
try-and-skip shape as notification_lock.py and exists as a port because
RunPdmPollIfDue lives in application and may not import the adapter.
"""

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class IPdmPollLock(Protocol):
    def lock(self) -> AbstractAsyncContextManager[bool]:
        """Tries to take the poll-tick lock and yields whether it got it,
        releasing it when the `with` block exits. On SQLite it always yields
        True; see advisory_lock.py."""
        ...
