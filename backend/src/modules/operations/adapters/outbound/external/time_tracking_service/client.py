"""httpx-backed implementation of ITimeTrackingProvider against the time
tracking service's HTTP API (docs/reference/time-tracking-provider.md).

One instance owns one long-lived httpx.AsyncClient per connection (service
URL and API key fixed at construction), shared by every user's requests on
this worker. Every authenticated call carries the API key in `X-Api-Key`;
credentials only ever travel sealed, in a POST body. Redirects are never
followed, so the API key cannot travel to a redirect target.

Errors: transport failure is TimeTrackingUnavailableError. An error answer
carries a stable `code`, which maps onto the domain errors:
`credentials_rejected` to TimeTrackingAuthenticationFailedError,
`permission_denied` to TimeTrackingPermissionDeniedError, `binding_changed`
and `credentials_unreadable` to TimeTrackingBindingChangedError,
`period_invalid` to TimeTrackingPeriodInvalidError, `provider_unavailable`
to TimeTrackingUnavailableError, and everything else, a refused API key
included, to TimeTrackingProviderError. Nothing here logs headers or
bodies, and no exception message carries a credential or the API key.
"""

from typing import Any
from typing import NoReturn

import httpx
from pydantic import BaseModel
from pydantic import ValidationError

from src.modules.operations.adapters.outbound.external.time_tracking_service.models import ErrorBody
from src.modules.operations.adapters.outbound.external.time_tracking_service.models import Health
from src.modules.operations.adapters.outbound.external.time_tracking_service.models import Info
from src.modules.operations.adapters.outbound.external.time_tracking_service.models import (
    MonthAnswer,
)
from src.modules.operations.adapters.outbound.external.time_tracking_service.models import Status
from src.modules.operations.adapters.outbound.external.time_tracking_service.models import (
    Verification,
)
from src.modules.operations.adapters.outbound.external.time_tracking_service.models import (
    YearAnswer,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingBindingChangedError
from src.modules.operations.domain.errors import TimeTrackingPeriodInvalidError
from src.modules.operations.domain.errors import TimeTrackingPermissionDeniedError
from src.modules.operations.domain.errors import TimeTrackingProviderError
from src.modules.operations.domain.errors import TimeTrackingUnavailableError
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingMonthRead
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceInfo,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceStatus,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingVerification,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import TimeTrackingYearRead
from src.modules.platform.infrastructure.logging.logger import log

API_KEY_HEADER = "X-Api-Key"
TIMEOUT_SECONDS = 20.0
# A year reads up to twelve months from the system behind the service in
# one session, so it gets more time.
YEAR_TIMEOUT_SECONDS = 90.0

_ERRORS_BY_CODE: dict[str, type[Exception]] = {
    "credentials_rejected": TimeTrackingAuthenticationFailedError,
    "permission_denied": TimeTrackingPermissionDeniedError,
    "binding_changed": TimeTrackingBindingChangedError,
    "credentials_unreadable": TimeTrackingBindingChangedError,
    "period_invalid": TimeTrackingPeriodInvalidError,
    "provider_unavailable": TimeTrackingUnavailableError,
}


def _validation_summary(exc: ValidationError, limit: int = 5) -> str:
    """Where and why validation failed, without the offending values."""
    return ", ".join(
        f"{'.'.join(str(p) for p in err['loc']) or '<root>'} ({err['type']})"
        for err in exc.errors(include_input=False, include_url=False)[:limit]
    )


class HttpxTimeTrackingServiceClient:
    """ITimeTrackingProvider for one time tracking service. The factory
    caches one instance per connection and shares it on the event loop."""

    def __init__(
        self,
        connection: TimeTrackingServiceConnection,
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

    async def info(self) -> TimeTrackingServiceInfo:
        return self._parse(Info, await self._send("GET", "/api/v1/info")).to_info()

    async def status(self) -> TimeTrackingServiceStatus:
        return self._parse(Status, await self._send("GET", "/api/v1/status")).to_status()

    async def verify(self, sealed_credentials: str) -> TimeTrackingVerification:
        response = await self._send(
            "POST", "/api/v1/credentials/verify", body={"sealed_credentials": sealed_credentials}
        )
        return self._parse(Verification, response).to_verification()

    async def month(
        self, sealed_credentials: str, binding: str, year: int, month: int
    ) -> TimeTrackingMonthRead:
        response = await self._send(
            "POST",
            "/api/v1/months",
            body={
                "sealed_credentials": sealed_credentials,
                "binding": binding,
                "month": f"{year:04d}-{month:02d}",
            },
        )
        return self._parse(MonthAnswer, response).to_read()

    async def year(self, sealed_credentials: str, binding: str, year: int) -> TimeTrackingYearRead:
        response = await self._send(
            "POST",
            "/api/v1/years",
            body={"sealed_credentials": sealed_credentials, "binding": binding, "year": year},
            read_timeout=YEAR_TIMEOUT_SECONDS,
        )
        return self._parse(YearAnswer, response).to_read()

    async def _send(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        authenticated: bool = True,
        read_timeout: float = TIMEOUT_SECONDS,
    ) -> httpx.Response:
        headers = {API_KEY_HEADER: self._api_key} if authenticated else {}
        try:
            response = await self._client.request(
                method, path, headers=headers, json=body, timeout=read_timeout
            )
        except httpx.TransportError as exc:
            raise TimeTrackingUnavailableError(
                f"The time tracking service could not be reached ({type(exc).__name__})."
            ) from exc
        if not response.is_success:
            self._raise_for_error(response)
        return response

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> NoReturn:
        if 300 <= response.status_code < 400:
            raise TimeTrackingProviderError(
                f"The time tracking service answered with a redirect (HTTP "
                f"{response.status_code}), which is never followed."
            )
        try:
            error = ErrorBody.model_validate(response.json())
        except (ValueError, ValidationError):
            error = ErrorBody()
        if response.status_code == 401:
            raise TimeTrackingProviderError("The time tracking service refused Glados' API key.")
        error_type = _ERRORS_BY_CODE.get(error.code)
        if error_type is not None:
            raise error_type(error.message or f"The time tracking service reported {error.code}.")
        raise TimeTrackingProviderError(
            f"The time tracking service call failed with HTTP {response.status_code}"
            f" ({error.code or 'no error code'})."
        )

    @staticmethod
    def _parse[T: BaseModel](model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate(response.json())
        except ValueError as exc:
            if isinstance(exc, ValidationError):
                log.warning(
                    f"The time tracking service returned an unexpected {model.__name__} shape: "
                    f"{_validation_summary(exc)}"
                )
            raise TimeTrackingProviderError(
                f"The time tracking service returned an unexpected {model.__name__} answer."
            ) from exc
