"""
PdmCadSource turns the PDM settings into the CAD policy Catalogue's item use
cases follow: connected while PDM is switched on and configured, rows read
only only while connected and the read-only switch is on.
"""

import pytest

from src.modules.catalogue.api import CadPolicy
from src.modules.external_data.application.services.pdm_cad_source import PdmCadSource
from tests.factories import make_user
from tests.unit.made_item._helpers import make_pdm_settings
from tests.unit.made_item.fakes import FakeAdminSettingsRepository


@pytest.mark.parametrize(
    ("enabled", "read_only", "expected"),
    [
        (False, True, CadPolicy(connected=False, rows_read_only=False)),
        (True, False, CadPolicy(connected=True, rows_read_only=False)),
        (True, True, CadPolicy(connected=True, rows_read_only=True)),
    ],
)
async def test_the_policy_follows_the_pdm_settings(
    enabled: bool, read_only: bool, expected: CadPolicy
) -> None:
    settings = FakeAdminSettingsRepository(
        pdm=make_pdm_settings(enabled=enabled, cad_items_read_only=read_only)
    )

    assert await PdmCadSource(settings).policy() == expected


def test_the_system_user_is_never_held_to_the_ownership() -> None:
    policy = CadPolicy(connected=True, rows_read_only=True)

    assert policy.enforces_ownership_for(make_user()) is True
    assert policy.enforces_ownership_for(make_user(is_systemuser=True)) is False
