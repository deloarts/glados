"""
Pydantic wire models for the answers of the stock service, the contract
Glados defines in docs/reference/stock-service.md. Every model ignores
fields it does not name, so a service that adds fields changes nothing
here, and carries a `to_*` method converting it into the port's
dataclasses, so nothing outside this package sees the wire shape.
"""

from pydantic import BaseModel
from pydantic import ConfigDict

from src.modules.external_data.ports.outbound.stock_service_port import StockServiceInfo
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceStatus


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ErrorBody(_WireModel):
    code: str = ""
    message: str = ""


class Health(_WireModel):
    version: str


class Info(_WireModel):
    service: str
    version: str
    contract_version: str
    provider_label: str

    def to_info(self) -> StockServiceInfo:
        return StockServiceInfo(
            service=self.service,
            version=self.version,
            contract_version=self.contract_version,
            provider_label=self.provider_label,
        )


class Status(_WireModel):
    server_version: str

    def to_status(self) -> StockServiceStatus:
        return StockServiceStatus(server_version=self.server_version)
