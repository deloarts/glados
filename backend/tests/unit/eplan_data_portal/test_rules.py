"""tests/unit/eplan_data_portal/test_rules.py: the supplier code and the
settings rules."""

import pytest

from src.modules.catalogue.domain.errors import SupplierEdpCodeInvalidError
from src.modules.catalogue.domain.services.supplier_edp_code import normalize_edp_code
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    normalize_edp_base_url,
)
from src.modules.external_data.domain.errors import EdpSettingsInvalidError


def test_edp_code_is_trimmed_and_upper_case() -> None:
    assert normalize_edp_code(" sie ") == "SIE"
    assert normalize_edp_code("") is None
    assert normalize_edp_code(None) is None


@pytest.mark.parametrize("value", ["SIE CODE", "#SIE", "X" * 17])
def test_edp_code_refuses_anything_but_a_short_code(value: str) -> None:
    with pytest.raises(SupplierEdpCodeInvalidError):
        normalize_edp_code(value)


def test_edp_base_url_must_be_plain_https() -> None:
    assert normalize_edp_base_url(" https://portal.example.test/api/ ") == (
        "https://portal.example.test/api"
    )
    for bad in (
        "http://portal.example.test/api",
        "https://u:p@portal.example.test",
        "https://x?y=1",
    ):
        with pytest.raises(EdpSettingsInvalidError):
            normalize_edp_base_url(bad)


def test_edp_settings_cannot_be_enabled_without_a_token() -> None:
    with pytest.raises(EdpSettingsInvalidError):
        AdminEdpSettings(id=1, enabled=True).assert_valid()
    with pytest.raises(EdpSettingsInvalidError):
        AdminEdpSettings(id=1, pat="t", language="fr_FR").assert_valid()
