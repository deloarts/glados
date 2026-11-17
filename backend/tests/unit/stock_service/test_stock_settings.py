"""
The stock service settings entity and the in-stack service URL rule it
shares with the time tracking service: when the service counts as
configured and ready, that enabling needs a URL and an API key, and which
URLs are accepted.
"""

import pytest

from src.modules.external_data.application.services.stock_service import contract_supported
from src.modules.external_data.application.services.stock_service import service_connection
from src.modules.external_data.domain.entities.admin_settings.stock import AdminStockSettings
from src.modules.external_data.domain.errors import StockServiceNotConfiguredError
from src.shared_kernel.domain.services.service_url import normalize_service_url


def test_the_defaults_are_switched_off_and_not_configured() -> None:
    settings = AdminStockSettings(id=1)

    assert settings.is_configured is False
    assert settings.is_ready is False
    settings.assert_valid()


def test_ready_needs_enabled_url_and_api_key() -> None:
    settings = AdminStockSettings(
        id=1, enabled=True, service_url="http://stock:3200", api_key="secret-value"
    )

    assert settings.is_ready is True
    assert "secret-value" not in repr(settings)
    assert service_connection(settings).service_url == "http://stock:3200"


@pytest.mark.parametrize(("service_url", "api_key"), [("", "key"), ("http://stock:3200", None)])
def test_enabling_without_url_or_api_key_is_refused(service_url: str, api_key: str | None) -> None:
    settings = AdminStockSettings(id=1, enabled=True, service_url=service_url, api_key=api_key)

    with pytest.raises(StockServiceNotConfiguredError):
        settings.assert_valid()


def test_service_urls_are_trimmed_and_plain_http_is_accepted() -> None:
    assert normalize_service_url(" http://stock:3200/ ") == "http://stock:3200"
    assert normalize_service_url("https://stock.example.test/api/") == (
        "https://stock.example.test/api"
    )
    assert normalize_service_url("  ") == ""


@pytest.mark.parametrize(
    "url",
    [
        "ftp://stock.example.test",
        "http://",
        "http://user:pass@stock.example.test",
        "http://stock.example.test/?q=1",
        "http://stock.example.test/#top",
        "http://stock.example.test:99999",
    ],
)
def test_unsafe_service_urls_are_refused(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_service_url(url)


@pytest.mark.parametrize(
    ("version", "supported"), [("0.1", True), ("0.1.4", True), ("0.2", False), ("1.0", False)]
)
def test_contract_support_is_decided_by_major_and_minor(version: str, supported: bool) -> None:
    assert contract_supported(version) is supported
