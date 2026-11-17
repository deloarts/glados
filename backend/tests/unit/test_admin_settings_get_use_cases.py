"""
The 14 new use_cases/admin_settings/get_*.py classes that replace
admin_settings.py's inline `has_permission` checks (15 including
GetPdmSettings).
Each test proves the read:settings guard fires *before* any collaborator
is touched, via the `_Boom` idiom (test_item_file_permissions.py:103):
a repo whose every attribute access raises, so a guard that ran after a
repo call (or didn't run at all) would fail loudly, not silently pass.
Positive-path field mapping is covered by the adapter-level tests
(test_api_admin_settings_auth.py etc.) and by
tests/unit/admin_settings/'s own AdminSettingsMapper coverage.
"""

import pytest

from src.modules.catalogue.application.use_cases.admin_settings.get_made_item_settings import (
    GetMadeItemSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.get_order_settings import (
    GetOrderSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_settings import (
    GetPdmSettings,
)
from src.modules.fulfillment.application.use_cases.admin_settings.get_production_settings import (
    GetProductionSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_auth_settings import (
    GetAuthSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_branding_settings import (
    GetBrandingSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_feature_settings import (
    GetFeatureSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_general_settings import (
    GetGeneralSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_host_settings import (
    GetHostSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_mail_settings import (
    GetMailSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_maintenance_settings import (
    GetMaintenanceSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_notification_settings import (
    GetNotificationSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_retention_settings import (
    GetRetentionSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_security_settings import (
    GetSecuritySettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_storage_settings import (
    GetStorageSettings,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.admin_settings.fakes import FakePdmFileSnapshotRepository


class _Boom:
    """Any attribute access explodes, proves the permission check happens
    before any collaborator is touched (test_item_file_permissions.py's
    idiom)."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"repository was used before the permission check ({name})")


NO_PERMS = make_user(permissions=[])


def _build(use_case_cls, repo, snapshot_repo):
    """GetPdmSettings is the one domain that also reads the file snapshots
    (for the counts on the settings page); every other reader takes the
    settings repo alone."""
    if use_case_cls is GetPdmSettings:
        return use_case_cls(repo, snapshot_repo)
    return use_case_cls(repo)


@pytest.mark.parametrize(
    "use_case_cls",
    [
        GetAuthSettings,
        GetMailSettings,
        GetStorageSettings,
        GetSecuritySettings,
        GetFeatureSettings,
        GetGeneralSettings,
        GetBrandingSettings,
        GetNotificationSettings,
        GetMaintenanceSettings,
        GetRetentionSettings,
        GetOrderSettings,
        GetMadeItemSettings,
        GetPdmSettings,
        GetProductionSettings,
    ],
)
async def test_get_settings_guard_fires_before_the_repo_is_touched(use_case_cls):
    with pytest.raises(InsufficientPermissionsError, match="read:settings"):
        await _build(use_case_cls, _Boom(), _Boom()).execute(actor=NO_PERMS)


async def test_get_host_settings_guard_fires_before_the_repo_is_touched():
    # /host is the one domain needing an extra `domain` constructor arg
    # (cfg.domain, not stored on the repo), same shape as GetAllAdminSettings.
    with pytest.raises(InsufficientPermissionsError, match="read:settings"):
        await GetHostSettings(_Boom(), "example.com").execute(actor=NO_PERMS)


@pytest.mark.parametrize(
    ("use_case_cls", "attr"),
    [
        (GetAuthSettings, "auth"),
        (GetMailSettings, "mail"),
        (GetStorageSettings, "storage"),
        (GetSecuritySettings, "security"),
        (GetFeatureSettings, "features"),
        (GetGeneralSettings, "general"),
        (GetBrandingSettings, "branding"),
        (GetNotificationSettings, "notifications"),
        (GetMaintenanceSettings, "maintenance"),
        (GetRetentionSettings, "retention"),
        (GetOrderSettings, "orders"),
        (GetMadeItemSettings, "made_items"),
        (GetPdmSettings, "pdm"),
        (GetProductionSettings, "production"),
    ],
)
async def test_get_settings_returns_the_mapped_result_for_a_permitted_actor(use_case_cls, attr):
    repo = FakeAdminSettingsRepository()
    actor = make_user(permissions=["read:settings"])
    result = await _build(use_case_cls, repo, FakePdmFileSnapshotRepository()).execute(actor=actor)
    assert result.id == getattr(repo, attr).id
