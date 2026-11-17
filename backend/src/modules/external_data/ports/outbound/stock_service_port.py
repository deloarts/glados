"""
Provider-neutral access to the stock system. Glados never talks to a stock
system itself: a stock service in the same stack does, and this port is the
contract Glados defines for it (docs/reference/stock-service.md). The
application layer calls the port, never httpx directly; the HTTP
implementation lives in
src/modules/external_data/adapters/outbound/external/stock_service/.

The contract covers the connection so far: reachability, the service's
self-description and its view of the system behind it. Errors are the
domain's StockService* exceptions (unavailable, provider error).
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class StockServiceConnection:
    """Where the service runs and the API key Glados calls it with. The key
    is hidden from repr, so a connection never leaks it into a log line."""

    service_url: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class StockServiceInfo:
    """What the service reports about itself without touching the system
    behind it: its name and version, the contract version it implements and
    the label Glados shows for the system behind it."""

    service: str
    version: str
    contract_version: str
    provider_label: str


@dataclass(frozen=True)
class StockServiceStatus:
    """The connection test's view of the system behind the service."""

    server_version: str


@runtime_checkable
class IStockService(Protocol):
    async def health(self) -> str:
        """Unauthenticated reachability probe returning the service version."""
        ...

    async def info(self) -> StockServiceInfo:
        """Checks the API key and reads the service's self-description."""
        ...

    async def status(self) -> StockServiceStatus:
        """Probes the system behind the service."""
        ...


# Builds (or returns the shared) client for a connection, so the admin
# connection test can probe unsaved settings.
type IStockServiceFactory = Callable[[StockServiceConnection], IStockService]
