"""
A fake stock service for the stock service tests: synthetic answers only,
and every call recorded so a test can assert what Glados asked for.
"""

from src.modules.external_data.ports.outbound.stock_service_port import StockServiceConnection
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceInfo
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceStatus


class FakeStockService:
    """Records every call by name. `fail_on` maps a call name to an
    exception to raise, and `contract_version` is what `info` reports."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_on: dict[str, Exception] = {}
        self.connections: list[StockServiceConnection] = []
        self.contract_version = "0.1"

    def factory(self, connection: StockServiceConnection) -> "FakeStockService":
        self.connections.append(connection)
        return self

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if name in self.fail_on:
            raise self.fail_on[name]

    async def health(self) -> str:
        self._record("health")
        return "0.1.0"

    async def info(self) -> StockServiceInfo:
        self._record("info")
        return StockServiceInfo(
            service="stock-service-fake",
            version="0.1.0",
            contract_version=self.contract_version,
            provider_label="Example Stock",
        )

    async def status(self) -> StockServiceStatus:
        self._record("status")
        return StockServiceStatus(server_version="1.2.3")
