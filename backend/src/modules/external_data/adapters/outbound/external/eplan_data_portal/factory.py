"""
Builds a Data Portal client from a connection, the seam
IEplanDataPortalFactory names, so the use cases reach the portal without
importing the adapter and the admin test can probe an unsaved token.
Clients are cached per connection in a small LRU GatewayCache, so calls
against the saved settings reuse one httpx client and its keep-alive
connections; close_eplan_data_portals closes them on shutdown.
"""

from src.modules.external_data.adapters.outbound.external.eplan_data_portal.client import (
    HttpxEplanDataPortal,
)
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortal
from src.modules.platform.adapters.outbound.external._gateway_cache import GatewayCache

_MAX_CACHED_CLIENTS = 4

_clients: GatewayCache[EdpConnection, HttpxEplanDataPortal] = GatewayCache(
    HttpxEplanDataPortal, _MAX_CACHED_CLIENTS
)


def create_eplan_data_portal(connection: EdpConnection) -> IEplanDataPortal:
    """Return the shared client for the given connection."""
    return _clients.get(connection)


async def close_eplan_data_portals() -> None:
    """Close every cached client. Called on shutdown."""
    await _clients.aclose_all()
