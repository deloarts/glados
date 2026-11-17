"""
Probes a vault with connection settings that have not been saved yet, so an
admin can validate a configuration before switching PDM on. Named Verify
rather than Test for the same reason as verify_ldap_connection.py: pytest
collects `Test*` classes and would otherwise warn on import.

Unlike LDAP, PDM authenticates with a stored service-account password
rather than the end user's own credentials, so the probe accepts an empty
password to mean "use the one already saved" instead of requiring the
admin to retype it on every test. Nothing is persisted here, not even on
success.
"""

from src.modules.external_data.application.dto.admin_settings_dto.pdm import PdmConnectionTestResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    VerifyPdmConnectionCommand,
)
from src.modules.external_data.domain.errors import PdmNotConfiguredError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGatewayFactory
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class VerifyPdmConnection:
    def __init__(
        self,
        gateway_factory: IPdmGatewayFactory,
        repo: IExternalDataSettingsRepository,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._gateway_factory = gateway_factory
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: VerifyPdmConnectionCommand
    ) -> PdmConnectionTestResult:
        """Reachability probe (unauthenticated version() call) followed by an
        authenticate() with the given or stored password.

        Raises PdmNotConfiguredError when a required field is missing and
        there is no stored password to fall back on, PdmAuthenticationFailedError
        when the vault rejected the credentials, and lets PdmUnavailableError
        through when the server could not be reached at all.
        """
        SettingsRules.assert_can_write(actor)

        base_url = cmd.base_url.strip()
        vault_name = cmd.vault_name.strip()
        username = cmd.username.strip()
        if not base_url or not vault_name or not username:
            raise PdmNotConfiguredError(
                "base_url, vault_name and username are required to test the connection."
            )

        password = cmd.password if cmd.password else (await self._repo.get_pdm()).password
        if not password:
            raise PdmNotConfiguredError(
                "No password was supplied and none is stored to fall back on."
            )

        connection = PdmConnection(
            base_url=base_url,
            vault_name=vault_name,
            verify_certificate=cmd.verify_certificate,
            timeout_seconds=cmd.timeout_seconds,
        )
        gateway = self._gateway_factory(connection)
        # Nothing is written here, so ending the read transaction only hands
        # the connection back to the pool for the two HTTP round trips.
        if self._uow is not None:
            await self._uow.commit()
        version = await gateway.version()
        auth_result = await gateway.authenticate(username, password)

        log.info("PDM connection test succeeded.")
        return PdmConnectionTestResult(
            product_name=version.product_name,
            app_version=version.app_version,
            user_id=auth_result.user_id,
        )
