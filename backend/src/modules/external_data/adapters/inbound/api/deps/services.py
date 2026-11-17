"""Adapter and service factories, and the services one process shares
between requests."""

from src.modules.external_data.adapters.outbound.external.eplan_data_portal.factory import (
    create_eplan_data_portal,
)
from src.modules.external_data.adapters.outbound.external.pdm.catalogue import (
    OPERATIONS as PDM_OPERATIONS,
)
from src.modules.external_data.adapters.outbound.external.pdm.factory import create_pdm_gateway
from src.modules.external_data.adapters.outbound.external.stock_service.factory import (
    create_stock_service,
)
from src.modules.external_data.application.services.pdm_trigger_rate_limiter import (
    PdmTriggerRateLimiter,
)
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGatewayFactory
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmOperationSpec
from src.modules.external_data.ports.outbound.stock_service_port import IStockServiceFactory


def get_pdm_gateway_factory() -> IPdmGatewayFactory:
    """The factory itself, for PdmSessionService and the admin test-connection
    use case, which must reach vaults that are not necessarily the saved
    settings."""
    return create_pdm_gateway


def get_eplan_data_portal_factory() -> IEplanDataPortalFactory:
    """The EPLAN Data Portal client factory, for the lookups and the admin
    connection test, which may probe an unsaved token."""
    return create_eplan_data_portal


def get_stock_service_factory() -> IStockServiceFactory:
    """The stock service client factory, for the admin connection test,
    which may probe unsaved settings."""
    return create_stock_service


def get_pdm_catalogue() -> tuple[PdmOperationSpec, ...]:
    """The static PDM Web API operation catalogue, for the admin API
    console's listing and invoke use cases."""
    return PDM_OPERATIONS


# One per process, because its window spans requests.
_pdm_trigger_rate_limiter = PdmTriggerRateLimiter()


def get_pdm_trigger_rate_limiter() -> PdmTriggerRateLimiter:
    return _pdm_trigger_rate_limiter
