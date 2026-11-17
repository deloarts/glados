"""httpx-backed implementation of IStockService against the stock service's
HTTP API (docs/reference/stock-service.md).

One instance owns one long-lived httpx.AsyncClient per connection (service
URL and API key fixed at construction), shared by every request on this
worker. Every authenticated call carries the API key in `X-Api-Key`.
Redirects are never followed, so the API key cannot travel to a redirect
target.

Errors: transport failure is StockServiceUnavailableError. An error answer
carries a stable `code`: `provider_unavailable` maps to
StockServiceUnavailableError, and everything else, a refused API key
included, to StockServiceProviderError. Nothing here logs headers or
bodies, and no exception message carries the API key.
"""

from typing import NoReturn

import httpx
from pydantic import BaseModel
from pydantic import ValidationError

from src.modules.external_data.adapters.outbound.external.stock_service.models import ErrorBody
from src.modules.external_data.adapters.outbound.external.stock_service.models import Health
from src.modules.external_data.adapters.outbound.external.stock_service.models import Info
from src.modules.external_data.adapters.outbound.external.stock_service.models import Status
from src.modules.external_data.domain.errors import StockServiceProviderError
from src.modules.external_data.domain.errors import StockServiceUnavailableError
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceConnection
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceInfo
from src.modules.external_data.ports.outbound.stock_service_port import StockServiceStatus
from src.modules.platform.infrastructure.logging.logger import log

API_KEY_HEADER = "X-Api-Key"
TIMEOUT_SECONDS = 20.0

_ERRORS_BY_CODE: dict[str, type[Exception]] = {
    "provider_unavailable": StockServiceUnavailableError,
}


def _validation_summary(exc: ValidationError, limit: int = 5) -> str:
    """Where and why validation failed, without the offending values."""
    return ", ".join(
        f"{'.'.join(str(p) for p in err['loc']) or '<root>'} ({err['type']})"
        for err in exc.errors(include_input=False, include_url=False)[:limit]
    )


class HttpxStockServiceClient:
    """IStockService for one stock service. The factory caches one instance
    per connection and shares it on the event loop."""

    def __init__(
        self,
        connection: StockServiceConnection,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = connection.api_key
        self._client = httpx.AsyncClient(
            base_url=connection.service_url,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> str:
        response = await self._send("GET", "/health", authenticated=False)
        return self._parse(Health, response).version

    async def info(self) -> StockServiceInfo:
        return self._parse(Info, await self._send("GET", "/api/v1/info")).to_info()

    async def status(self) -> StockServiceStatus:
        return self._parse(Status, await self._send("GET", "/api/v1/status")).to_status()

    async def _send(self, method: str, path: str, *, authenticated: bool = True) -> httpx.Response:
        headers = {API_KEY_HEADER: self._api_key} if authenticated else {}
        try:
            response = await self._client.request(method, path, headers=headers)
        except httpx.TransportError as exc:
            raise StockServiceUnavailableError(
                f"The stock service could not be reached ({type(exc).__name__})."
            ) from exc
        if not response.is_success:
            self._raise_for_error(response)
        return response

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> NoReturn:
        if 300 <= response.status_code < 400:
            raise StockServiceProviderError(
                f"The stock service answered with a redirect (HTTP "
                f"{response.status_code}), which is never followed."
            )
        try:
            error = ErrorBody.model_validate(response.json())
        except (ValueError, ValidationError):
            error = ErrorBody()
        if response.status_code == 401:
            raise StockServiceProviderError("The stock service refused Glados' API key.")
        error_type = _ERRORS_BY_CODE.get(error.code)
        if error_type is not None:
            raise error_type(error.message or f"The stock service reported {error.code}.")
        raise StockServiceProviderError(
            f"The stock service call failed with HTTP {response.status_code}"
            f" ({error.code or 'no error code'})."
        )

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate(response.json())
        except ValueError as exc:
            if isinstance(exc, ValidationError):
                log.warning(
                    f"The stock service returned an unexpected {model.__name__} shape: "
                    f"{_validation_summary(exc)}"
                )
            raise StockServiceProviderError(
                f"The stock service returned an unexpected {model.__name__} answer."
            ) from exc
