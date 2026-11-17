"""
The weather service: forecasts from MET Norway and the place search of
Nominatim, both free for any use and both credited on the screen.

Both services ask a client to name itself, so every request carries a
User-Agent with Glados' version and the organisation's contact from the
general settings. Forecasts are cached in the process per rounded
coordinate, day count and timezone, so many screens showing the same town
cost one call every 15 minutes. When a fetch fails, a forecast fetched
within the last 12 hours stands in with its own fetch time; without one
the call raises WeatherUnavailableError. Place searches are spaced at least
a second apart, as Nominatim's usage policy asks, and an answer is kept for
a day.
"""

import asyncio
import time
from collections import OrderedDict
from datetime import timedelta
from typing import Any
from typing import Final
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

import httpx

from src.modules.operations.adapters.outbound.external.weather import met_norway
from src.modules.operations.adapters.outbound.external.weather import nominatim
from src.modules.operations.domain.errors import WeatherUnavailableError
from src.modules.operations.ports.outbound.weather_port import WeatherClientContact
from src.modules.operations.ports.outbound.weather_port import WeatherForecast
from src.modules.operations.ports.outbound.weather_port import WeatherPlace
from src.modules.platform.const import VERSION
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.clock import now_utc

TIMEOUT_SECONDS: Final = 10.0
FRESH_FOR: Final = timedelta(minutes=15)
STANDS_IN_FOR: Final = timedelta(hours=12)
PLACES_KEPT_FOR_SECONDS: Final = 24 * 3600
SEARCH_SPACING_SECONDS: Final = 1.1
# Bounds both caches when many screens show many towns; the oldest goes.
_MAX_CACHED: Final = 256

_ForecastKey = tuple[float, float, int, str]
_PlacesKey = tuple[str, str, str]


def user_agent(contact: WeatherClientContact) -> str:
    """Glados and its version, then the organisation's website and email
    where the settings have them, as both services ask."""
    details = "; ".join(part for part in (contact.website, contact.email) if part)
    base = f"Glados/{VERSION}"
    return f"{base} ({details})" if details else base


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class WeatherService:
    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        search_spacing_seconds: float = SEARCH_SPACING_SECONDS,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=False, transport=transport
        )
        self._forecasts: OrderedDict[_ForecastKey, WeatherForecast] = OrderedDict()
        self._places: OrderedDict[_PlacesKey, tuple[float, list[WeatherPlace]]] = OrderedDict()
        self._forecast_lock = asyncio.Lock()
        self._search_lock = asyncio.Lock()
        self._search_spacing = search_spacing_seconds
        self._last_search = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, params: dict[str, Any], contact: WeatherClientContact) -> Any:
        try:
            response = await self._client.get(
                url,
                params=params,
                headers={"User-Agent": user_agent(contact), "Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("The weather service did not answer: %s", type(e).__name__)
            raise WeatherUnavailableError("The weather service did not answer.") from e

    @staticmethod
    def _remember[K, V](cache: OrderedDict[K, V], key: K, value: V) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > _MAX_CACHED:
            cache.popitem(last=False)

    async def forecast(
        self,
        latitude: float,
        longitude: float,
        days: int,
        timezone: str,
        contact: WeatherClientContact,
    ) -> WeatherForecast:
        key = (round(latitude, 2), round(longitude, 2), days, timezone)
        cached = self._forecasts.get(key)
        if cached is not None and now_utc() - cached.fetched_at < FRESH_FOR:
            return cached
        # One fetch at a time, so screens refreshing together do not all
        # call the service for the same town.
        async with self._forecast_lock:
            cached = self._forecasts.get(key)
            if cached is not None and now_utc() - cached.fetched_at < FRESH_FOR:
                return cached
            try:
                body = await self._get(
                    met_norway.FORECAST_URL, {"lat": key[0], "lon": key[1]}, contact
                )
                fetched = met_norway.parse_locationforecast(body, _zone(timezone), days, now_utc())
            except (WeatherUnavailableError, KeyError, TypeError, ValueError) as e:
                if cached is not None and now_utc() - cached.fetched_at < STANDS_IN_FOR:
                    return cached
                if isinstance(e, WeatherUnavailableError):
                    raise
                log.warning("The weather service sent an unusable forecast: %s", e)
                raise WeatherUnavailableError("The weather service sent an unusable answer.") from e
            self._remember(self._forecasts, key, fetched)
            return fetched

    async def search_places(
        self, query: str, country_code: str, language: str, contact: WeatherClientContact
    ) -> list[WeatherPlace]:
        key = (query.casefold(), country_code.upper(), language)
        kept = self._places.get(key)
        if kept is not None and time.monotonic() - kept[0] < PLACES_KEPT_FOR_SECONDS:
            return kept[1]
        async with self._search_lock:
            wait = self._last_search + self._search_spacing - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                body = await self._get(
                    nominatim.SEARCH_URL,
                    nominatim.search_params(query, country_code, language),
                    contact,
                )
            finally:
                self._last_search = time.monotonic()
        places = nominatim.parse_places(body)
        self._remember(self._places, key, (time.monotonic(), places))
        return places


_service: WeatherService | None = None


def get_weather_service() -> WeatherService:
    """The process wide weather service, built on first use."""
    global _service
    if _service is None:
        _service = WeatherService()
    return _service


async def close_weather_service() -> None:
    """Closes the weather service's connection pool. Called on shutdown."""
    global _service
    if _service is not None:
        await _service.aclose()
        _service = None
