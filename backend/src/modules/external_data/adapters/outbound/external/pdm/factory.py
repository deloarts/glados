"""
Builds a PDM gateway from a connection. It is the seam IPdmGatewayFactory
names, and it lets the admin test-connection use case probe unsaved settings
without importing the concrete adapter into the application layer, same
shape as the LDAP authenticator factory.

Gateways are cached per PdmConnection in a small LRU `GatewayCache`, so
every call against the saved connection reuses one httpx.AsyncClient and its
keep-alive connections. `close_pdm_gateways` closes whatever is cached on
shutdown.
"""

from src.modules.external_data.adapters.outbound.external.pdm.client import HttpxPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.platform.adapters.outbound.external._gateway_cache import GatewayCache

MAX_CACHED_GATEWAYS = 4

_gateways: GatewayCache[PdmConnection, HttpxPdmGateway] = GatewayCache(
    HttpxPdmGateway, MAX_CACHED_GATEWAYS
)


def create_pdm_gateway(connection: PdmConnection) -> IPdmGateway:
    """Return the shared gateway for the given connection."""
    return _gateways.get(connection)


async def close_pdm_gateways() -> None:
    """Close every cached gateway's HTTP client. Called on shutdown."""
    await _gateways.aclose_all()
