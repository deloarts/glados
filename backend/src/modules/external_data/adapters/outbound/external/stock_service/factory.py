"""
Builds a stock service client from a connection. It is the seam
IStockServiceFactory names, so the use cases reach the service without
importing the concrete adapter, and the admin connection test can probe
unsaved settings.

Clients are cached per connection in a small LRU `GatewayCache`, so every
call against the saved settings reuses one httpx.AsyncClient and its
keep-alive connections. `close_stock_service_clients` closes whatever is
cached on shutdown.
"""

from src.modules.external_data.adapters.outbound.external.stock_service.client import (
    HttpxStockServiceClient,
)
from src.modules.external_data.ports.outbound.stock_service_port import IStockService
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceConnection
from src.modules.platform.adapters.outbound.external._gateway_cache import GatewayCache

_MAX_CACHED_CLIENTS = 4

_clients: GatewayCache[StockServiceConnection, HttpxStockServiceClient] = GatewayCache(
    HttpxStockServiceClient, _MAX_CACHED_CLIENTS
)


def create_stock_service(connection: StockServiceConnection) -> IStockService:
    """Return the shared client for the given connection."""
    return _clients.get(connection)


async def close_stock_service_clients() -> None:
    """Close every cached client's HTTP connection pool. Called on shutdown."""
    await _clients.aclose_all()
