"""Tests a stock service with settings that need not be saved yet: the
service's self-description, which needs the API key, and its view of the
system behind it. Nothing is stored. Named Verify rather than Test, like
verify_pdm_connection.py, because pytest collects `Test*` classes.

The answer says whether the service speaks a contract version Glados
supports. The client never follows a redirect, so the test cannot be used
to chase one.
"""

from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    StockServiceTestResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    VerifyStockServiceCommand,
)
from src.modules.external_data.application.services.stock_service import contract_supported
from src.modules.external_data.domain.errors import StockServiceNotConfiguredError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.stock_service_port import IStockServiceFactory
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceConnection
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class VerifyStockService:
    def __init__(
        self,
        service_factory: IStockServiceFactory,
        repo: IExternalDataSettingsRepository,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._service_factory = service_factory
        self._repo = repo
        self._uow = uow

    async def execute(self, actor: User, cmd: VerifyStockServiceCommand) -> StockServiceTestResult:
        SettingsRules.assert_can_write(actor)

        stored = await self._repo.get_stock()
        service_url = cmd.service_url if cmd.service_url is not None else stored.service_url
        api_key = (
            cmd.api_key.get_secret_value().strip()
            if cmd.api_key is not None and cmd.api_key.get_secret_value().strip()
            else stored.api_key
        )
        if not service_url or not api_key:
            raise StockServiceNotConfiguredError(
                "A service URL and an API key are required to test the connection."
            )

        service = self._service_factory(
            StockServiceConnection(service_url=service_url, api_key=api_key)
        )
        # Nothing is written, so ending the read transaction only hands the
        # connection back to the pool for the HTTP round trips.
        if self._uow is not None:
            await self._uow.commit()
        info = await service.info()
        status = await service.status()

        log.info(
            "Stock service test succeeded (%s %s, server %s).",
            info.service,
            info.version,
            status.server_version,
        )
        return StockServiceTestResult(
            service=info.service,
            service_version=info.version,
            contract_version=info.contract_version,
            contract_supported=contract_supported(info.contract_version),
            provider_label=info.provider_label,
            server_version=status.server_version,
        )
