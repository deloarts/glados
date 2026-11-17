"""Domain entity for the stock service settings singleton.
docs/STOCK_SERVICE.md describes every setting.

Glados reaches the stock system only through a stock service in the same
stack, so the settings name that service and the API key Glados calls it
with. The service URL follows the rule of every in-stack service
(`assert_plain_http_url`): plain http is accepted, user information, a
query and a fragment are not.
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.external_data.domain.errors import StockServiceNotConfiguredError
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminStockSettings(Entity):
    """Stock service settings singleton. `api_key` is plaintext in memory
    and encrypted at rest; it never leaves the server."""

    enabled: bool = False
    service_url: str = ""
    api_key: str | None = field(default=None, repr=False)

    @property
    def is_configured(self) -> bool:
        """Whether Glados can reach the service: a URL and an API key."""
        return bool(self.service_url) and bool(self.api_key)

    @property
    def is_ready(self) -> bool:
        """Switched on and reachable."""
        return self.enabled and self.is_configured

    def assert_valid(self) -> None:
        """Raises when the stock service is enabled without a service URL
        and an API key."""
        if self.enabled and not self.is_configured:
            raise StockServiceNotConfiguredError(
                "Enabling the stock service requires the service URL and the API key."
            )
