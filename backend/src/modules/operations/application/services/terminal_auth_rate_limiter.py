"""
In-process sliding-window limiter for the terminal challenge and session
endpoints, keyed by client address and endpoint: 60 requests per 60 seconds
each. Like PdmTriggerRateLimiter it guards against a misbehaving or hostile
caller hammering an unauthenticated endpoint, not a precise cross-worker
quota, so every gunicorn worker keeping its own budget is acceptable.

A healthy display signs in about every 15 minutes, so the budget leaves room
for many displays behind one proxy address restarting at once.

One instance must live for the whole lifetime of a worker process (see
get_terminal_auth_rate_limiter in deps/services.py), or its window would never fill.
"""

import threading
import time
from collections import defaultdict
from collections import deque

from src.modules.operations.domain.errors import TerminalAuthRateLimitedError

DEFAULT_MAX_REQUESTS = 60
DEFAULT_WINDOW_SECONDS = 60.0
# Keys idle for longer than this are dropped on the next check, so the map
# cannot grow without bound under a stream of new addresses.
_PRUNE_EVERY = 1000


class TerminalAuthRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._checks = 0

    def check(self, endpoint: str, client_ip: str | None) -> None:
        """Raises TerminalAuthRateLimitedError when one more call would take
        this address past the limit for `endpoint`; records it otherwise."""
        key = f"{endpoint}:{client_ip or 'unknown'}"
        now = time.monotonic()
        with self._lock:
            self._checks += 1
            if self._checks % _PRUNE_EVERY == 0:
                self._prune(now)
            hits = self._hits[key]
            while hits and now - hits[0] > self._window_seconds:
                hits.popleft()
            if len(hits) >= self._max_requests:
                raise TerminalAuthRateLimitedError(
                    f"Too many terminal {endpoint} requests from this address; try again shortly."
                )
            hits.append(now)

    def _prune(self, now: float) -> None:
        stale = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] > self._window_seconds
        ]
        for key in stale:
            del self._hits[key]
