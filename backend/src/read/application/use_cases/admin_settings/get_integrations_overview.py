"""
Which integrations are switched on and configured, for the overview on the
admin Host tab. It reads the settings of several modules, so it sits in the
read tier. Requires read:settings.

Unlike the services panel, which probes connections live, this only reads
the stored settings, so it answers whether an integration is set up, not
whether its remote end currently answers.
"""

from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.read.application.dto.admin_settings_dto.integrations_overview import (
    IntegrationsOverviewResult,
)
from src.read.application.dto.admin_settings_dto.integrations_overview import IntegrationState
from src.read.application.dto.admin_settings_dto.integrations_overview import (
    IntegrationStatusResult,
)
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository


def _state(enabled: bool, configured: bool) -> IntegrationState:
    if not enabled:
        return "off"
    return "active" if configured else "incomplete"


class GetIntegrationsOverview:
    def __init__(self, repo: IAdminSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> IntegrationsOverviewResult:
        SettingsRules.assert_can_read(actor)

        mail = await self._repo.get_mail()
        auth = await self._repo.get_auth()
        security = await self._repo.get_security()
        storage = await self._repo.get_storage()
        features = await self._repo.get_features()
        pdm = await self._repo.get_pdm()
        time_tracking = await self._repo.get_time_tracking()
        stock = await self._repo.get_stock()
        edp = await self._repo.get_edp()
        try:
            agents = await self._repo.get_agents()
        except RuntimeError:
            # Seeded on every start; only a database that never ran the seed
            # lacks the row, and there agent access counts as off.
            agents = AdminAgentSettings(id=1)

        mail_ready = mail.enabled and bool(mail.host and mail.from_address)
        # The local provider needs no connection details; every other
        # provider stores files in a bucket it must be told about.
        storage_ready = storage.enabled and (
            storage.provider == "local" or bool(storage.bucket_name)
        )
        states: list[tuple[str, IntegrationState]] = [
            ("mail", _state(mail.enabled, mail_ready)),
            ("email_notifications", _state(features.enable_email_notifications, mail_ready)),
            ("ldap", _state(auth.ldap_enabled, bool(auth.ldap_host))),
            ("api_keys", _state(security.enable_api_key_auth, True)),
            ("terminals", _state(security.enable_terminals, True)),
            ("storage", _state(storage.enabled, storage_ready)),
            (
                "backups",
                _state(storage.backup_enabled, storage_ready and bool(storage.backup_cron)),
            ),
            ("pdm", _state(pdm.enabled, pdm.is_configured)),
            ("time_tracking", _state(time_tracking.enabled, time_tracking.is_ready)),
            ("stock_service", _state(stock.enabled, stock.is_ready)),
            ("eplan_data_portal", _state(edp.enabled, edp.is_configured)),
            ("agents", _state(agents.enabled, agents.is_ready)),
        ]
        return IntegrationsOverviewResult(
            integrations=[IntegrationStatusResult(key=key, state=state) for key, state in states]
        )
