"""Helpers around the stock service: the connection a client is built from
and the contract minors Glados supports (docs/reference/stock-service.md).

Glados states the contract minors it was built against; a connection test
against a service speaking another one warns the admin.
"""

from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceConnection

SUPPORTED_CONTRACT_MINORS = frozenset({"0.1"})


def service_connection(settings: AdminStockSettings) -> StockServiceConnection:
    """The connection of the saved settings. Callers check is_configured."""
    return StockServiceConnection(service_url=settings.service_url, api_key=settings.api_key or "")


def contract_supported(contract_version: str) -> bool:
    """Whether the service's contract major.minor is one Glados supports."""
    return ".".join(contract_version.split(".")[:2]) in SUPPORTED_CONTRACT_MINORS
