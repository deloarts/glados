"""Tests a time tracking service with settings that need not be saved yet:
the service's self-description, which needs the API key, and its view of
the system behind it, which needs no user credentials. Nothing is stored.
Named Verify rather than Test, like verify_pdm_connection.py, because
pytest collects `Test*` classes.

The answer says whether the service speaks a contract version Glados
supports, whether Glados can collect the credential fields it asks for, and
whether the key it serves is the confirmed one; confirming is a separate
step (ConfirmTimeTrackingKey). The client never follows a redirect, so the
test cannot be used to chase one.
"""

from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    TimeTrackingServiceTestResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    VerifyTimeTrackingServiceCommand,
)
from src.modules.operations.application.services.time_tracking_service import contract_supported
from src.modules.operations.application.services.time_tracking_service import (
    credential_fields_supported,
)
from src.modules.operations.domain.errors import TimeTrackingNotConfiguredError
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class VerifyTimeTrackingService:
    def __init__(
        self,
        provider_factory: ITimeTrackingProviderFactory,
        repo: IOperationsSettingsRepository,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: VerifyTimeTrackingServiceCommand
    ) -> TimeTrackingServiceTestResult:
        SettingsRules.assert_can_write(actor)

        stored = await self._repo.get_time_tracking()
        service_url = cmd.service_url if cmd.service_url is not None else stored.service_url
        api_key = (
            cmd.api_key.get_secret_value().strip()
            if cmd.api_key is not None and cmd.api_key.get_secret_value().strip()
            else stored.api_key
        )
        if not service_url or not api_key:
            raise TimeTrackingNotConfiguredError(
                "A service URL and an API key are required to test the connection."
            )

        provider = self._provider_factory(
            TimeTrackingServiceConnection(service_url=service_url, api_key=api_key)
        )
        # Nothing is written, so ending the read transaction only hands the
        # connection back to the pool for the HTTP round trips.
        if self._uow is not None:
            await self._uow.commit()
        info = await provider.info()
        status = await provider.status()

        log.info(
            "Time tracking service test succeeded (%s %s, server %s).",
            info.service,
            info.version,
            status.server_version,
        )
        return TimeTrackingServiceTestResult(
            service=info.service,
            service_version=info.version,
            contract_version=info.contract_version,
            contract_supported=contract_supported(info.contract_version),
            credential_fields_supported=credential_fields_supported(info.credential_fields),
            provider_label=info.provider_label,
            credential_public_key=info.credential_public_key,
            credential_key_id=info.credential_key_id,
            key_confirmed=(
                service_url == stored.service_url
                and info.credential_key_id == stored.credential_key_id
                and info.credential_public_key == stored.credential_public_key
            ),
            server_version=status.server_version,
            default_project=status.default_project,
        )
