"""
HttpxTimeTrackingServiceClient against httpx.MockTransport: no network, no
real service, synthetic data only. Covers the request shapes (API key on
every call but /health, sealed credentials only in POST bodies), the
answers in the provider contract's shape becoming domain values, the error
codes mapping onto the domain errors, a refused API key, redirects never
being followed, transport failures, and unexpected answers.
"""

import json
from collections.abc import Callable
from datetime import UTC
from datetime import date
from datetime import datetime

import httpx
import pytest

from src.modules.operations.adapters.outbound.external.time_tracking_service.client import (
    HttpxTimeTrackingServiceClient,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingBindingChangedError
from src.modules.operations.domain.errors import TimeTrackingPeriodInvalidError
from src.modules.operations.domain.errors import TimeTrackingPermissionDeniedError
from src.modules.operations.domain.errors import TimeTrackingProviderError
from src.modules.operations.domain.errors import TimeTrackingUnavailableError
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingAccountFormat
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBookingDirection
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDayStatus
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)

Handler = Callable[[httpx.Request], httpx.Response]

SERVICE_URL = "http://time-tracking.example.test:3100"
API_KEY = "test-service-api-key"
SEALED = "sealed-value"
BINDING = "b" * 32


def make_client(handler: Handler) -> HttpxTimeTrackingServiceClient:
    return HttpxTimeTrackingServiceClient(
        TimeTrackingServiceConnection(service_url=SERVICE_URL, api_key=API_KEY),
        transport=httpx.MockTransport(handler),
    )


def error(status: int, code: str, message: str = "Something failed.") -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": message})


def month_payload(first_day: str = "2026-09-01", last_day: str = "2026-09-30") -> dict[str, object]:
    return {
        "first_day": first_day,
        "last_day": last_day,
        "days": [
            {
                "date": "2026-09-30",
                "target_seconds": 27720,
                "worked_seconds": None,
                "first_in": "2026-09-30T05:58:00Z",
                "last_out": None,
                "status": "open",
                "bookings": [{"at": "2026-09-30T05:58:00Z", "direction": "in"}],
                "a_future_field": 1,
            },
            {
                "date": "2026-09-29",
                "shift_name": "Full time",
                "shift_short_name": "FT",
                "target_seconds": 27720,
                "worked_seconds": 30000,
                "running_balance_seconds": 5880,
                "first_in": "2026-09-29T06:43:00Z",
                "last_out": "2026-09-29T15:03:00Z",
                "status": "normal",
                "bookings": [
                    {"at": "2026-09-29T15:03:00Z", "direction": "out"},
                    {"at": "2026-09-29T06:43:00Z", "direction": "in"},
                ],
            },
        ],
        "accounts": [
            {
                "account_id": 11,
                "name": "Balance",
                "short_name": "BAL",
                "format": "duration_clock",
                "pre": 3600,
                "sum": 2280,
                "post": 5880,
            },
            {
                "account_id": 12,
                "name": "Points",
                "short_name": "PTS",
                "format": "a_format_glados_does_not_know",
                "pre": 1,
                "sum": 0,
                "post": 1,
            },
        ],
    }


async def test_health_needs_no_api_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})

    assert await make_client(handler).health() == "0.1.0"
    assert seen[0].url == httpx.URL(f"{SERVICE_URL}/health")
    assert "X-Api-Key" not in seen[0].headers


async def test_info_sends_the_api_key_and_maps_the_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET" and request.url.path == "/api/v1/info"
        assert request.headers["X-Api-Key"] == API_KEY
        return httpx.Response(
            200,
            json={
                "service": "example-time-service",
                "version": "0.1.0",
                "contract_version": "0.1",
                "provider_label": "Example Time",
                "credential_fields": [
                    {"name": "user", "kind": "text", "required": True, "max_length": 128},
                    {"name": "password", "kind": "secret", "required": True, "max_length": 256},
                ],
                "credential_public_key": "public-key",
                "credential_key_id": "0123456789abcdef",
                "binding": BINDING,
            },
        )

    info = await make_client(handler).info()

    assert (info.provider_label, info.contract_version, info.credential_key_id) == (
        "Example Time",
        "0.1",
        "0123456789abcdef",
    )
    assert [f.name for f in info.credential_fields] == ["user", "password"]


async def test_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/status"
        return httpx.Response(
            200,
            json={"provider_label": "X", "server_version": "1.2", "default_project": "DEMO"},
        )

    status = await make_client(handler).status()

    assert (status.server_version, status.default_project) == ("1.2", "DEMO")


async def test_verify_posts_the_sealed_value_in_the_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "binding": BINDING,
                "employee_name": "Doe, Jane",
                "rights": {"days": False, "month": True, "year": True},
            },
        )

    verification = await make_client(handler).verify(SEALED)

    request = seen[0]
    assert request.method == "POST" and request.url.path == "/api/v1/credentials/verify"
    assert json.loads(request.content) == {"sealed_credentials": SEALED}
    assert SEALED not in str(request.url)
    assert verification.binding == BINDING
    assert (verification.rights.days, verification.rights.month) == (False, True)


async def test_month_maps_the_contract_values() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "employee_name": "Doe, Jane",
                "month": month_payload(),
                "fetched_at": "2026-09-30T08:15:00Z",
            },
        )

    read = await make_client(handler).month(SEALED, BINDING, 2026, 9)

    assert seen[0].url.path == "/api/v1/months"
    assert json.loads(seen[0].content) == {
        "sealed_credentials": SEALED,
        "binding": BINDING,
        "month": "2026-09",
    }
    month = read.month
    assert [d.day for d in month.days] == [date(2026, 9, 29), date(2026, 9, 30)]
    closed, today = month.days
    assert closed.status is TimeTrackingDayStatus.NORMAL
    assert closed.running_balance_seconds == 5880
    assert [b.direction for b in closed.bookings] == [
        TimeTrackingBookingDirection.IN,
        TimeTrackingBookingDirection.OUT,
    ]
    assert today.shift_name is None and today.running_balance_seconds is None
    assert today.bookings[0].at == datetime(2026, 9, 30, 5, 58, tzinfo=UTC)
    assert [a.format for a in month.accounts] == [
        TimeTrackingAccountFormat.DURATION_CLOCK,
        TimeTrackingAccountFormat.RAW,
    ]
    assert read.fetched_at == datetime(2026, 9, 30, 8, 15, tzinfo=UTC)


async def test_year_maps_every_month() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/years"
        assert json.loads(request.content)["year"] == 2026
        return httpx.Response(
            200,
            json={
                "employee_name": "Doe, Jane",
                "year": 2026,
                "months": [
                    month_payload("2026-01-01", "2026-01-31"),
                    month_payload("2026-02-01", "2026-02-28"),
                ],
                "fetched_at": "2026-09-30T08:15:00Z",
            },
        )

    read = await make_client(handler).year(SEALED, BINDING, 2026)

    assert [m.first_day for m in read.months] == [date(2026, 1, 1), date(2026, 2, 1)]


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (403, "credentials_rejected", TimeTrackingAuthenticationFailedError),
        (403, "permission_denied", TimeTrackingPermissionDeniedError),
        (409, "binding_changed", TimeTrackingBindingChangedError),
        (422, "credentials_unreadable", TimeTrackingBindingChangedError),
        (422, "period_invalid", TimeTrackingPeriodInvalidError),
        (503, "provider_unavailable", TimeTrackingUnavailableError),
        (502, "provider_error", TimeTrackingProviderError),
        (422, "request_invalid", TimeTrackingProviderError),
        (500, "something_new", TimeTrackingProviderError),
    ],
)
async def test_error_codes_map_onto_domain_errors(
    status: int, code: str, expected: type[Exception]
) -> None:
    client = make_client(lambda request: error(status, code))

    with pytest.raises(expected):
        await client.month(SEALED, BINDING, 2026, 9)


async def test_a_refused_api_key_is_a_provider_error_without_the_key() -> None:
    client = make_client(lambda request: error(401, "api_key_invalid"))

    with pytest.raises(TimeTrackingProviderError, match="API key") as exc_info:
        await client.info()
    assert API_KEY not in str(exc_info.value)


async def test_an_error_without_a_json_body_is_a_provider_error() -> None:
    client = make_client(lambda request: httpx.Response(500, text="<html>"))

    with pytest.raises(TimeTrackingProviderError, match="HTTP 500"):
        await client.status()


async def test_redirects_are_never_followed() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://elsewhere.example.test/"})

    with pytest.raises(TimeTrackingProviderError, match="redirect"):
        await make_client(handler).verify(SEALED)
    assert len(seen) == 1


async def test_transport_failure_maps_to_unavailable_without_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(TimeTrackingUnavailableError) as exc_info:
        await make_client(handler).verify(SEALED)
    assert SEALED not in str(exc_info.value) and API_KEY not in str(exc_info.value)


@pytest.mark.parametrize(
    "body",
    [
        {"binding": BINDING},
        {"binding": BINDING, "employee_name": "x", "rights": {"days": "maybe"}},
    ],
)
async def test_unexpected_answers_are_provider_errors(body: dict[str, object]) -> None:
    client = make_client(lambda request: httpx.Response(200, json=body))

    with pytest.raises(TimeTrackingProviderError, match="unexpected"):
        await client.verify(SEALED)


async def test_naive_booking_times_are_refused() -> None:
    payload = month_payload()
    days = payload["days"]
    assert isinstance(days, list)
    days[0]["bookings"] = [{"at": "2026-09-30T07:58:00", "direction": "in"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"employee_name": "x", "month": payload, "fetched_at": "2026-09-30T08:15:00Z"},
        )

    with pytest.raises(TimeTrackingProviderError):
        await make_client(handler).month(SEALED, BINDING, 2026, 9)
