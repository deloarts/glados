"""
In-process sliding-window limiter for the PDM file-changed trigger
endpoints (POST {API_KEY}/pdm/files/changed, its /batch form and the PAT
surface's /batch form): 300 files per 60 seconds per actor id, a batch
counting each of its files. The actor of an API key is the key's own
service account and the actor of a PAT is the user who owns it, so every
key and every user has a budget of its own. Deliberately in-process rather
than Redis or a DB table: this guards against a misbehaving caller (the
vault add-in looping, a bad Dispatch script) hammering the endpoint, not a
precise cross-worker quota, and gunicorn's several workers each holding
their own independent budget is an acceptable, much simpler approximation
of the same guard.

One instance must live for the whole lifetime of a worker process (see
get_pdm_trigger_rate_limiter in deps/services.py) so its window is shared across
requests; a fresh instance per request would never accumulate any hits
and could never actually limit anything.
"""

import threading
import time
from collections import defaultdict
from collections import deque

from src.modules.external_data.domain.errors import PdmTriggerRateLimitedError

DEFAULT_MAX_REQUESTS = 300
DEFAULT_WINDOW_SECONDS = 60.0


class PdmTriggerRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, actor_id: int, cost: int = 1) -> None:
        """Raises PdmTriggerRateLimitedError when `cost` more calls would take
        `actor_id` past `max_requests` within the trailing `window_seconds`;
        otherwise records them and returns normally. A batch trigger costs
        one call per file, so batching saves round trips, not budget."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[actor_id]
            while hits and now - hits[0] > self._window_seconds:
                hits.popleft()
            if len(hits) + cost > self._max_requests:
                raise PdmTriggerRateLimitedError(
                    f"Actor #{actor_id} exceeded {self._max_requests} PDM trigger "
                    f"requests per {int(self._window_seconds)}s; try again shortly."
                )
            hits.extend([now] * cost)
