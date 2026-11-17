"""
A small LRU cache of HTTP gateways keyed by their connection settings,
shared by the PDM gateway and time tracking service client factories.

Every call against the same connection reuses one gateway, and with it one
httpx.AsyncClient and its keep-alive connections, instead of opening (and
never closing) a fresh client per call. The cache holds at most `max_size`
gateways. A changed connection builds a new gateway, and the evicted one is
left to garbage collection rather than closed, because an in-flight request
may still be using it. `aclose_all` closes whatever is cached on shutdown.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable
from collections.abc import Hashable
from typing import Generic
from typing import Protocol
from typing import TypeVar


class _Closable(Protocol):
    async def aclose(self) -> None: ...


K = TypeVar("K", bound=Hashable)
G = TypeVar("G", bound=_Closable)


class GatewayCache(Generic[K, G]):
    """Thread-safe LRU cache of gateways built by `build` for each key."""

    def __init__(self, build: Callable[[K], G], max_size: int) -> None:
        self._build = build
        self._max_size = max_size
        self._gateways: OrderedDict[K, G] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> G:
        """Return the cached gateway for `key`, building it on first use and
        evicting the least recently used one when the cache is full."""
        with self._lock:
            gateway = self._gateways.get(key)
            if gateway is None:
                gateway = self._build(key)
                self._gateways[key] = gateway
                while len(self._gateways) > self._max_size:
                    self._gateways.popitem(last=False)
            else:
                self._gateways.move_to_end(key)
            return gateway

    async def aclose_all(self) -> None:
        """Empty the cache and close every gateway it held."""
        with self._lock:
            gateways = list(self._gateways.values())
            self._gateways.clear()
        for gateway in gateways:
            await gateway.aclose()

    def clear(self) -> None:
        """Empty the cache without closing anything, for tests whose event
        loop the cached clients were bound to is already gone."""
        with self._lock:
            self._gateways.clear()

    def __len__(self) -> int:
        return len(self._gateways)
