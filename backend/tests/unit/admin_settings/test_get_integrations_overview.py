"""
Unit tests for GetIntegrationsOverview, the Host tab's summary of which
integrations are switched on and configured. No database, no HTTP.
"""

from dataclasses import replace

import pytest

from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.read.application.use_cases.admin_settings.get_integrations_overview import (
    GetIntegrationsOverview,
)
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository


class _Repo(FakeAdminSettingsRepository):
    """Adds the sections of the modules above Platform the overview reads."""

    def __init__(self) -> None:
        super().__init__()
        self.time_tracking = AdminTimeTrackingSettings(
            id=1,
            enabled=False,
            service_url="",
            api_key=None,
            credential_public_key=None,
            credential_key_id=None,
            provider_label=None,
            privacy_policy_url=None,
        )
        self.stock = AdminStockSettings(id=1)
        self.edp = AdminEdpSettings(id=1)
        self.agents: AdminAgentSettings | None = AdminAgentSettings(id=1)

    async def get_time_tracking(self) -> AdminTimeTrackingSettings:
        return self.time_tracking

    async def get_stock(self) -> AdminStockSettings:
        return self.stock

    async def get_edp(self) -> AdminEdpSettings:
        return self.edp

    async def get_agents(self) -> AdminAgentSettings:
        if self.agents is None:
            raise RuntimeError("not seeded")
        return self.agents


async def _states(repo: _Repo) -> dict[str, str]:
    actor = make_user(permissions=[Permission.READ_SETTINGS])
    result = await GetIntegrationsOverview(repo).execute(actor)  # type: ignore[arg-type]
    return {entry.key: entry.state for entry in result.integrations}


async def test_requires_read_settings() -> None:
    with pytest.raises(InsufficientPermissionsError):
        await GetIntegrationsOverview(_Repo()).execute(make_user(permissions=[]))  # type: ignore[arg-type]


async def test_reports_every_integration_from_the_stored_settings() -> None:
    states = await _states(_Repo())

    assert states == {
        "mail": "off",
        # Switched on, but mail is off, so nothing would be sent.
        "email_notifications": "incomplete",
        "ldap": "off",
        "api_keys": "off",
        "terminals": "active",
        # The local provider needs no connection details.
        "storage": "active",
        "backups": "off",
        "pdm": "off",
        "time_tracking": "off",
        "stock_service": "off",
        "eplan_data_portal": "off",
        "agents": "off",
    }


async def test_switched_on_without_its_details_is_incomplete() -> None:
    repo = _Repo()
    repo.mail = replace(repo.mail, enabled=True, host="")
    repo.storage = replace(repo.storage, provider="s3", bucket_name=None, backup_enabled=True)
    repo.stock = AdminStockSettings(id=1, enabled=True)

    states = await _states(repo)

    assert states["mail"] == "incomplete"
    assert states["storage"] == "incomplete"
    assert states["backups"] == "incomplete"
    assert states["stock_service"] == "incomplete"


async def test_switched_on_and_configured_is_active() -> None:
    repo = _Repo()
    repo.mail = replace(repo.mail, enabled=True, host="smtp.example.com", from_address="a@b.c")
    repo.stock = AdminStockSettings(
        id=1, enabled=True, service_url="https://stock.example", api_key="k"
    )
    repo.edp = AdminEdpSettings(id=1, enabled=True, pat="secret")

    states = await _states(repo)

    assert states["mail"] == "active"
    assert states["email_notifications"] == "active"
    assert states["stock_service"] == "active"
    assert states["eplan_data_portal"] == "active"


async def test_unseeded_agent_settings_count_as_off() -> None:
    repo = _Repo()
    repo.agents = None

    assert (await _states(repo))["agents"] == "off"
