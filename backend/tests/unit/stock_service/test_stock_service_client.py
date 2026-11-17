"""
HttpxStockServiceClient against httpx.MockTransport: no network, no real
service, synthetic data only. Covers the API key on every call but
/health, the answers in the contract's shape becoming the port's values,
the error codes, a refused API key, redirects never being followed,
transport failures and unexpected answers.
"""

from collections.abc import Callable

import httpx
import pytest

from src.modules.external_data.adapters.outbound.external.stock_service.client import (
    HttpxStockServiceClient,
)
from src.modules.external_data.domain.errors import StockServiceProviderError
from src.modules.external_data.domain.errors import StockServiceUnavailableError
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceConnection

Handler = Callable[[httpx.Request], httpx.Response]

SERVICE_URL = "http://stock.example.test:3200"
API_KEY = "test-stock-api-key"

INFO = {
    "service": "stock-service-fake",
    "version": "0.1.0",
    "contract_version": "0.1",
    "provider_label": "Example Stock",
    "extra": "ignored",
}


def make_client(handler: Handler) -> HttpxStockServiceClient:
    return HttpxStockServiceClient(
        StockServiceConnection(service_url=SERVICE_URL, api_key=API_KEY),
        transport=httpx.MockTransport(handler),
    )


async def test_health_is_unauthenticated_and_returns_the_version() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})

    assert await make_client(handler).health() == "0.1.0"
    assert seen[0].url.path == "/health"
    assert "x-api-key" not in seen[0].headers


async def test_info_and_status_carry_the_api_key_and_map_the_answer() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/v1/info":
            return httpx.Response(200, json=INFO)
        return httpx.Response(200, json={"server_version": "4.2"})

    client = make_client(handler)
    info = await client.info()
    status = await client.status()

    assert info.service == "stock-service-fake"
    assert info.contract_version == "0.1"
    assert info.provider_label == "Example Stock"
    assert status.server_version == "4.2"
    assert [r.url.path for r in seen] == ["/api/v1/info", "/api/v1/status"]
    assert all(r.headers["x-api-key"] == API_KEY for r in seen)


async def test_a_refused_api_key_is_a_provider_error_without_the_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "api_key_invalid", "message": "No."})

    with pytest.raises(StockServiceProviderError) as exc:
        await make_client(handler).info()

    assert "API key" in str(exc.value)
    assert API_KEY not in str(exc.value)


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (503, "provider_unavailable", StockServiceUnavailableError),
        (502, "provider_error", StockServiceProviderError),
        (500, "", StockServiceProviderError),
    ],
)
async def test_error_codes_map_onto_the_domain_errors(
    status: int, code: str, expected: type[Exception]
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"code": code, "message": "Failed."})

    with pytest.raises(expected):
        await make_client(handler).status()


async def test_a_redirect_is_never_followed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://elsewhere.example.test/"})

    with pytest.raises(StockServiceProviderError, match="redirect"):
        await make_client(handler).info()


async def test_a_transport_failure_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(StockServiceUnavailableError):
        await make_client(handler).health()


async def test_an_unexpected_answer_is_a_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"service": "missing the rest"})

    with pytest.raises(StockServiceProviderError, match="unexpected Info"):
        await make_client(handler).info()
