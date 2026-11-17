"""
Reads the Locationforecast 2.0 answer of MET Norway (api.met.no), the
Norwegian Meteorological Institute's free forecast for any place on earth.
Its data is licensed under CC BY 4.0, which only asks for the credit the
display shows.

The answer is a time series, hourly for the first days and in six hour
steps after that. Each entry has the instant values and summaries for the
next one, six or twelve hours. The weather now is the first entry; a day
is the entries falling on that calendar day in the screen's timezone, with
its highest and lowest temperature and its precipitation counted once per
period. Its symbol is the twelve hour summary of the daytime, from the
entry nearest 06:00, or else the symbol of the period nearest noon.
"""

from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Final
from zoneinfo import ZoneInfo

from src.modules.operations.ports.outbound.weather_port import WeatherDay
from src.modules.operations.ports.outbound.weather_port import WeatherForecast
from src.modules.operations.ports.outbound.weather_port import WeatherNow

FORECAST_URL: Final = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
ATTRIBUTION: Final = "MET Norway"
_MS_TO_KMH: Final = 3.6


def _number(values: dict[str, Any], key: str) -> float | None:
    value = values.get(key)
    return float(value) if isinstance(value, int | float) else None


def _symbol(period: dict[str, Any] | None) -> str | None:
    if not period:
        return None
    symbol = (period.get("summary") or {}).get("symbol_code")
    return str(symbol) if symbol else None


class _Day:
    def __init__(self) -> None:
        self.temperatures: list[float] = []
        self.precipitation: float | None = None
        # (hours from noon, symbol) of the best period seen so far.
        self.symbol: tuple[float, str] | None = None
        # (hours from 06:00, symbol) of the best twelve hour summary.
        self.daytime: tuple[float, str] | None = None

    def add_precipitation(self, amount: float | None) -> None:
        if amount is not None:
            self.precipitation = (self.precipitation or 0.0) + amount

    def offer_symbol(self, local: datetime, symbol: str | None, hours: int) -> None:
        """Keeps the symbol of the period whose middle lies nearest noon."""
        if symbol is None:
            return
        middle = local + timedelta(hours=hours / 2)
        distance = abs(middle.hour + middle.minute / 60 - 12)
        if self.symbol is None or distance < self.symbol[0]:
            self.symbol = (distance, symbol)

    def offer_daytime(self, local: datetime, symbol: str | None) -> None:
        """Keeps the twelve hour summary starting nearest 06:00."""
        if symbol is None:
            return
        distance = abs(local.hour + local.minute / 60 - 6)
        if distance <= 3 and (self.daytime is None or distance < self.daytime[0]):
            self.daytime = (distance, symbol)

    def add_entry(self, local: datetime, data: dict[str, Any]) -> None:
        """Takes the temperatures and symbols of one entry of the series."""
        temperature = _number((data.get("instant") or {}).get("details") or {}, "air_temperature")
        if temperature is not None:
            self.temperatures.append(temperature)
        one, six = data.get("next_1_hours"), data.get("next_6_hours")
        self.offer_daytime(local, _symbol(data.get("next_12_hours")))
        if six:
            details = six.get("details") or {}
            for key in ("air_temperature_max", "air_temperature_min"):
                value = _number(details, key)
                if value is not None:
                    self.temperatures.append(value)
            self.offer_symbol(local, _symbol(six), 6)
        elif one:
            self.offer_symbol(local, _symbol(one), 1)

    def add_period_precipitation(
        self, moment: datetime, data: dict[str, Any], counted_until: datetime | None
    ) -> datetime | None:
        """Adds the precipitation of the entry's shortest period unless an
        earlier period already covered this moment, which happens where the
        series turns from hourly to six hourly. Returns the moment up to
        which precipitation is counted now."""
        if counted_until is not None and moment < counted_until:
            return counted_until
        for key, hours in (("next_1_hours", 1), ("next_6_hours", 6)):
            period = data.get(key)
            if period:
                self.add_precipitation(_number(period.get("details") or {}, "precipitation_amount"))
                return moment + timedelta(hours=hours)
        return counted_until

    @property
    def best_symbol(self) -> str | None:
        if self.daytime is not None:
            return self.daytime[1]
        return self.symbol[1] if self.symbol is not None else None


def _now(first: dict[str, Any]) -> WeatherNow:
    """The weather now, from the first entry of the series."""
    instant = first["instant"]["details"]
    symbol_now = _symbol(first.get("next_1_hours") or first.get("next_6_hours"))
    wind = _number(instant, "wind_speed")
    return WeatherNow(
        temperature=_number(instant, "air_temperature"),
        symbol=symbol_now,
        wind_speed=round(wind * _MS_TO_KMH, 1) if wind is not None else None,
        is_day=not (symbol_now or "").endswith("_night"),
    )


def parse_locationforecast(
    body: dict[str, Any], zone: ZoneInfo, days: int, fetched_at: datetime
) -> WeatherForecast:
    """A forecast from the Locationforecast answer: now and today plus the
    `days` after it, as far as the answer reaches. Raises KeyError or
    ValueError on an answer without a time series."""
    series = body["properties"]["timeseries"]
    if not series:
        raise ValueError("The forecast holds no time series.")

    now = _now(series[0]["data"])
    today = fetched_at.astimezone(zone).date()
    last_day = today + timedelta(days=days)
    by_day: dict[date, _Day] = {}
    # Precipitation is summed per period, and a period already counted is
    # not counted again where the series turns from hourly to six hourly.
    counted_until: datetime | None = None
    for entry in series:
        moment = datetime.fromisoformat(str(entry["time"]).replace("Z", "+00:00"))
        local = moment.astimezone(zone)
        if local.date() > last_day:
            break
        if local.date() < today:
            continue
        data = entry.get("data") or {}
        day = by_day.setdefault(local.date(), _Day())
        day.add_entry(local, data)
        counted_until = day.add_period_precipitation(moment, data, counted_until)

    return WeatherForecast(
        now=now,
        days=[
            WeatherDay(
                day=day_date,
                symbol=day.best_symbol,
                temperature_max=max(day.temperatures) if day.temperatures else None,
                temperature_min=min(day.temperatures) if day.temperatures else None,
                precipitation_mm=(
                    round(day.precipitation, 1) if day.precipitation is not None else None
                ),
            )
            for day_date, day in sorted(by_day.items())
        ],
        fetched_at=fetched_at,
        attribution=ATTRIBUTION,
    )
