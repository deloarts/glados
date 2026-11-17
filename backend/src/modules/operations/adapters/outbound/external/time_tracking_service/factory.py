"""
Builds a time tracking service client from a connection. It is the seam
ITimeTrackingProviderFactory names, so the use cases reach the service
without importing the concrete adapter, and the admin connection test can
probe unsaved settings.

Clients are cached per connection in a small LRU `GatewayCache`, so every
call against the saved settings reuses one httpx.AsyncClient and its
keep-alive connections. `close_time_tracking_clients` closes whatever is
cached on shutdown.
"""

from src.modules.operations.adapters.outbound.external.time_tracking_service.client import (
    HttpxTimeTrackingServiceClient,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import ITimeTrackingProvider
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)
from src.modules.platform.adapters.outbound.external._gateway_cache import GatewayCache

_MAX_CACHED_CLIENTS = 4

_clients: GatewayCache[TimeTrackingServiceConnection, HttpxTimeTrackingServiceClient] = (
    GatewayCache(HttpxTimeTrackingServiceClient, _MAX_CACHED_CLIENTS)
)


def create_time_tracking_provider(
    connection: TimeTrackingServiceConnection,
) -> ITimeTrackingProvider:
    """Return the shared client for the given connection."""
    return _clients.get(connection)


async def close_time_tracking_clients() -> None:
    """Close every cached client's HTTP connection pool. Called on shutdown."""
    await _clients.aclose_all()
