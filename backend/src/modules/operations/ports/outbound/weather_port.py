"""
The weather service an infoscreen's weather widget reads: places found by
name within one country, and the forecast for a place's coordinates.

Only a town's name and its rounded centre ever reach the service, never an
address. The services ask every client to name itself, so each call carries
the organisation's contact from the general settings, never a user's. An
adapter raises WeatherUnavailableError when the service cannot answer and
it has nothing it fetched before.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class WeatherClientContact:
    """How Glados names itself to the weather service: the organisation's
    contact email and website from the general settings, either may be
    missing."""

    email: str | None = None
    website: str | None = None


@dataclass(frozen=True)
class WeatherPlace:
    name: str
    region: str | None
    country_code: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WeatherNow:
    """`symbol` is the service's weather symbol for the coming hour, such as
    `partlycloudy_day`; the wind is in km/h."""

    temperature: float | None
    symbol: str | None
    wind_speed: float | None
    is_day: bool


@dataclass(frozen=True)
class WeatherDay:
    day: date
    symbol: str | None
    temperature_max: float | None
    temperature_min: float | None
    precipitation_mm: float | None


@dataclass(frozen=True)
class WeatherForecast:
    """The weather now and per day from today, as fetched at `fetched_at`,
    which lies in the past when the service failed and an earlier forecast
    stands in. `attribution` names the source the display has to credit."""

    now: WeatherNow
    days: list[WeatherDay]
    fetched_at: datetime
    attribution: str


@runtime_checkable
class IWeatherService(Protocol):
    async def forecast(
        self,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
        contact: WeatherClientContact,
    ) -> WeatherForecast:
        """The forecast for today and the `days` after it, the days counted
        in `timezone` (an IANA name)."""
        ...

    async def search_places(
        self, query: str, country_code: str, language: str, contact: WeatherClientContact
    ) -> list[WeatherPlace]:
        """Towns whose name matches `query` in the country, best match first,
        named in `language` (ISO 639-1) where the service knows that name."""
        ...
