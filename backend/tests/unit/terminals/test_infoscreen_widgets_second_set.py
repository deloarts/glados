"""The weather, products, projects and machine detail widgets, the overdue
option of the deliveries widget, the signed drawing links, and the weather
service adapter with its cache."""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.modules.operations.adapters.outbound.external.weather import service as weather_service
from src.modules.operations.adapters.outbound.external.weather.met_norway import (
    parse_locationforecast,
)
from src.modules.operations.adapters.outbound.external.weather.nominatim import parse_places
from src.modules.operations.adapters.outbound.external.weather.service import WeatherService
from src.modules.operations.adapters.outbound.external.weather.service import user_agent
from src.modules.operations.domain.errors import InvalidInfoscreenConfigError
from src.modules.operations.domain.errors import WeatherUnavailableError
from src.modules.operations.domain.value_objects.infoscreen import DeliveriesExpectedWidget
from src.modules.operations.domain.value_objects.infoscreen import MachineDetailWidget
from src.modules.operations.domain.value_objects.infoscreen import ProductsWidget
from src.modules.operations.domain.value_objects.infoscreen import ProjectsWidget
from src.modules.operations.domain.value_objects.infoscreen import WeatherWidget
from src.modules.operations.domain.value_objects.infoscreen import pages_to_data
from src.modules.operations.domain.value_objects.infoscreen import parse_pages
from src.modules.operations.domain.value_objects.infoscreen import parse_widget
from src.modules.operations.infrastructure.security.terminal_auth import create_drawing_token
from src.modules.operations.infrastructure.security.terminal_auth import create_thumbnail_token
from src.modules.operations.infrastructure.security.terminal_auth import read_drawing_token
from src.modules.operations.infrastructure.security.terminal_auth import read_thumbnail_token
from src.modules.operations.ports.outbound.weather_port import WeatherClientContact

_WEATHER: dict[str, Any] = {
    "type": "weather",
    "location_name": " Zell am See ",
    "region": "Salzburg",
    "country_code": "at",
    "latitude": 47.32234,
    "longitude": 12.79678,
}


# ── Widget configs ───────────────────────────────────────────────────────


def test_weather_keeps_a_town_rounded_to_two_decimals() -> None:
    widget = parse_widget(_WEATHER)
    assert widget == WeatherWidget(
        location_name="Zell am See",
        region="Salzburg",
        country_code="AT",
        latitude=47.32,
        longitude=12.8,
    )
    assert widget.days == 3 and widget.show_wind is False


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"location_name": "  "}, "location_name is required"),
        ({"country_code": "AUT"}, "two letter country code"),
        ({"latitude": 91}, "latitude must be between"),
        ({"longitude": "15"}, "longitude must be a number"),
        ({"days": 8}, "days must be between"),
    ],
)
def test_weather_refuses_a_bad_place(change: dict[str, Any], fragment: str) -> None:
    with pytest.raises(InvalidInfoscreenConfigError, match=fragment):
        parse_widget({**_WEATHER, **change})


def test_machine_detail_needs_a_machine() -> None:
    with pytest.raises(InvalidInfoscreenConfigError, match="machine_id must be a positive id"):
        parse_widget({"type": "machine_detail"})
    with pytest.raises(InvalidInfoscreenConfigError, match="next_count must be between 0 and 5"):
        parse_widget({"type": "machine_detail", "machine_id": 4, "next_count": 6})
    widget = parse_widget({"type": "machine_detail", "machine_id": 4, "next_count": 0})
    assert widget == MachineDetailWidget(machine_id=4, next_count=0)
    assert widget.show_drawing is True and widget.show_customer is False


def test_new_widgets_and_the_overdue_option_survive_a_round_trip() -> None:
    pages = parse_pages(
        [
            {
                "layout": "grid_2x2",
                "slots": [
                    _WEATHER,
                    {"type": "products", "show_projects": True},
                    {"type": "projects", "show_customer": True},
                    {"type": "deliveries_expected", "show_overdue": True},
                ],
            },
            {"layout": "full", "slots": [{"type": "deliveries_expected"}]},
        ]
    )
    assert pages[0].slots[1] == ProductsWidget(show_projects=True)
    assert pages[0].slots[2] == ProjectsWidget(show_customer=True)
    assert pages[0].slots[3] == DeliveriesExpectedWidget(show_overdue=True)
    assert pages[1].slots[0] == DeliveriesExpectedWidget(show_overdue=False)
    assert parse_pages(pages_to_data(pages)) == pages


# ── Drawing links ────────────────────────────────────────────────────────


def test_a_drawing_token_names_its_item_and_file_until_it_expires() -> None:
    now = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
    token = create_drawing_token(7, 42, now)
    claims = read_drawing_token(token, now)
    assert claims is not None and claims[:2] == (7, 42)
    assert read_drawing_token(token, now + timedelta(minutes=70)) is not None
    assert read_drawing_token(token, now + timedelta(minutes=75)) is None


def test_a_drawing_token_cannot_be_forged_or_swapped_for_a_thumbnail_token() -> None:
    now = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
    token = create_drawing_token(7, 42, now)
    assert read_drawing_token(token.replace(".42.", ".43.", 1), now) is None
    assert read_drawing_token(token[:-2] + "AA", now) is None
    thumbnail = create_thumbnail_token("made", 7, "thumbnail", now)
    assert read_drawing_token(thumbnail, now) is None
    assert read_thumbnail_token(token, now) is None


# ── Weather service ──────────────────────────────────────────────────────

_VIENNA = ZoneInfo("Europe/Vienna")
_CONTACT = WeatherClientContact(email="office@example.com", website="https://example.com")


def _entry(
    time: str,
    temperature: float,
    one: tuple[str, float] | None = None,
    six: tuple[str, float, float, float] | None = None,
    wind: float | None = None,
    twelve: str | None = None,
) -> dict[str, Any]:
    """One entry of a Locationforecast time series: the instant values, the
    next hour (symbol, mm), the next six hours (symbol, mm, max, min) and
    the next twelve hours' symbol."""
    data: dict[str, Any] = {
        "instant": {"details": {"air_temperature": temperature, "wind_speed": wind}}
    }
    if one:
        data["next_1_hours"] = {
            "summary": {"symbol_code": one[0]},
            "details": {"precipitation_amount": one[1]},
        }
    if six:
        data["next_6_hours"] = {
            "summary": {"symbol_code": six[0]},
            "details": {
                "precipitation_amount": six[1],
                "air_temperature_max": six[2],
                "air_temperature_min": six[3],
            },
        }
    if twelve:
        data["next_12_hours"] = {"summary": {"symbol_code": twelve}}
    return {"time": time, "data": data}


# 10 November 2026 in Vienna (UTC+1): hourly entries first, then six hourly.
_FORECAST_BODY: dict[str, Any] = {
    "properties": {
        "timeseries": [
            _entry("2026-11-10T09:00:00Z", 4.5, one=("cloudy", 0.0), wind=5.0),
            _entry("2026-11-10T10:00:00Z", 5.5, one=("lightrain", 0.4)),
            _entry("2026-11-10T11:00:00Z", 6.0, one=("rain", 1.1), six=("rain", 2.0, 7.0, 4.0)),
            _entry(
                "2026-11-11T05:00:00Z",
                1.0,
                six=("cloudy", 0.0, 3.0, 0.5),
                twelve="partlycloudy_day",
            ),
            _entry("2026-11-11T11:00:00Z", 6.0, six=("clearsky_day", 0.0, 8.0, 5.0)),
            _entry("2026-11-11T17:00:00Z", 2.0, six=("clearsky_night", 0.2, 3.0, -1.0)),
            _entry("2026-11-13T11:00:00Z", 3.0, six=("snow", 4.0, 3.0, 0.0)),
        ]
    }
}


def test_parse_locationforecast_reads_now_and_counts_days_in_the_timezone() -> None:
    fetched = datetime(2026, 11, 10, 9, 5, tzinfo=UTC)
    forecast = parse_locationforecast(_FORECAST_BODY, _VIENNA, 1, fetched)

    assert forecast.now.temperature == 4.5
    assert forecast.now.symbol == "cloudy"
    assert forecast.now.wind_speed == 18.0
    assert forecast.now.is_day is True
    assert forecast.attribution == "MET Norway"
    assert [d.day for d in forecast.days] == [date(2026, 11, 10), date(2026, 11, 11)]
    today, tomorrow = forecast.days
    assert (today.temperature_max, today.temperature_min) == (7.0, 4.0)
    # Hourly amounts are counted once; the six hour period starting at the
    # last hourly entry is not counted on top of it.
    assert today.precipitation_mm == 1.5
    # The period whose middle lies nearest noon: 11:00 to 12:00 local.
    assert today.symbol == "lightrain"
    assert (tomorrow.temperature_max, tomorrow.temperature_min) == (8.0, -1.0)
    # The twelve hour summary of the daytime wins over single periods.
    assert tomorrow.symbol == "partlycloudy_day"
    assert tomorrow.precipitation_mm == 0.2


def test_parse_locationforecast_refuses_an_empty_series() -> None:
    with pytest.raises(ValueError):
        parse_locationforecast({"properties": {"timeseries": []}}, _VIENNA, 1, datetime.now(UTC))


def test_parse_places_keeps_each_town_once_with_rounded_coordinates() -> None:
    places = parse_places(
        [
            {
                "lat": "47.3233",
                "lon": "12.7956",
                "name": "Zell am See",
                "address": {
                    "town": "Zell am See",
                    "state": "Salzburg",
                    "country_code": "at",
                },
            },
            {
                "lat": "47.3239",
                "lon": "12.7961",
                "name": "Zell am See",
                "address": {"state": "Salzburg", "country_code": "at"},
            },
            {"lat": "x", "lon": "15", "name": "Broken"},
            {"lat": "47.1", "lon": "15.2", "address": {"village": "Au", "country_code": "at"}},
        ]
    )
    assert [(p.name, p.region, p.country_code, p.latitude, p.longitude) for p in places] == [
        ("Zell am See", "Salzburg", "AT", 47.32, 12.8),
        ("Au", None, "AT", 47.1, 15.2),
    ]
    assert parse_places({"error": "x"}) == []


def test_the_user_agent_names_glados_and_the_organisation() -> None:
    assert user_agent(_CONTACT).endswith("(https://example.com; office@example.com)")
    assert user_agent(_CONTACT).startswith("Glados/")
    assert "(" not in user_agent(WeatherClientContact())


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 9, 5, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


async def test_the_service_caches_and_lets_an_earlier_forecast_stand_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _Clock()
    monkeypatch.setattr(weather_service, "now_utc", clock)
    calls: list[httpx.Request] = []
    failing = {"on": False}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if failing["on"]:
            return httpx.Response(429)
        return httpx.Response(200, json=_FORECAST_BODY)

    service = WeatherService(transport=httpx.MockTransport(handler))
    first = await service.forecast(47.3233, 12.7956, 1, "Europe/Vienna", _CONTACT)
    assert calls[0].url.params["lat"] == "47.32"
    assert calls[0].url.params["lon"] == "12.8"
    assert "office@example.com" in calls[0].headers["user-agent"]

    clock.now += timedelta(minutes=10)
    assert await service.forecast(47.32, 12.8, 1, "Europe/Vienna", _CONTACT) is first
    assert len(calls) == 1

    clock.now += timedelta(minutes=10)
    failing["on"] = True
    stand_in = await service.forecast(47.32, 12.8, 1, "Europe/Vienna", _CONTACT)
    assert stand_in is first and len(calls) == 2

    with pytest.raises(WeatherUnavailableError):
        await service.forecast(47.0, 15.0, 1, "Europe/Vienna", _CONTACT)

    clock.now += timedelta(hours=13)
    with pytest.raises(WeatherUnavailableError):
        await service.forecast(47.32, 12.8, 1, "Europe/Vienna", _CONTACT)
    await service.aclose()


async def test_the_place_search_asks_for_towns_spaced_and_keeps_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(weather_service.asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    service = WeatherService(transport=httpx.MockTransport(handler), search_spacing_seconds=60)
    assert await service.search_places("Zell am See", "AT", "de", _CONTACT) == []
    params = seen[0].url.params
    assert params["countrycodes"] == "at" and params["accept-language"] == "de"
    assert params["featureType"] == "settlement" and params["q"] == "Zell am See"
    assert "Glados/" in seen[0].headers["user-agent"]

    assert await service.search_places("zell am see", "at", "de", _CONTACT) == []
    assert len(seen) == 1

    await service.search_places("Kaprun", "AT", "de", _CONTACT)
    assert len(seen) == 2
    assert slept and slept[0] > 50
    await service.aclose()
