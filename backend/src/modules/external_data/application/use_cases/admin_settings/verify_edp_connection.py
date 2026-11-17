"""Probes the EPLAN Data Portal with the given or stored URL and token: one
authenticated read that proves the token is accepted. Stores nothing."""

from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    EdpConnectionTestResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    VerifyEdpConnectionCommand,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    normalize_edp_base_url,
)
from src.modules.external_data.domain.errors import EdpNotConfiguredError
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class VerifyEdpConnection:
    def __init__(
        self, repo: IExternalDataSettingsRepository, portal_factory: IEplanDataPortalFactory
    ) -> None:
        self._repo = repo
        self._portal_factory = portal_factory

    async def execute(
        self, actor: User, cmd: VerifyEdpConnectionCommand
    ) -> EdpConnectionTestResult:
        SettingsRules.assert_can_write(actor)
        stored = await self._repo.get_edp()
        base_url = normalize_edp_base_url(cmd.base_url) if cmd.base_url else stored.base_url
        pat = (cmd.pat or "").strip() or stored.pat
        if not pat:
            raise EdpNotConfiguredError("Enter a personal access token to test the connection.")
        portal = self._portal_factory(EdpConnection(base_url=base_url, pat=pat))
        info = await portal.test_connection()
        return EdpConnectionTestResult(authenticated=info.authenticated)
