"""
Reads the place search of Nominatim, the geocoder of OpenStreetMap, whose
data is licensed under the ODbL and credited in the location picker.

The public instance allows one request per second and no search as you
type, so the picker searches only when asked and the service spaces its
calls. Only settlements are asked for, since the widget keeps a town and
never an address.
"""

from typing import Any
from typing import Final

from src.modules.operations.ports.outbound.weather_port import WeatherPlace

SEARCH_URL: Final = "https://nominatim.openstreetmap.org/search"
MAX_PLACES: Final = 10
_NAME_KEYS: Final = ("city", "town", "village", "municipality", "hamlet", "suburb")


def search_params(query: str, country_code: str, language: str) -> dict[str, Any]:
    return {
        "q": query,
        "countrycodes": country_code.lower(),
        "format": "jsonv2",
        "addressdetails": 1,
        "featureType": "settlement",
        "limit": MAX_PLACES,
        "accept-language": language,
    }


def _coordinate(value: Any) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def parse_places(body: Any) -> list[WeatherPlace]:
    """The towns of a search answer, each name and region once, in the
    order Nominatim ranks them."""
    places: list[WeatherPlace] = []
    seen: set[tuple[str, str | None]] = set()
    for raw in body if isinstance(body, list) else []:
        if not isinstance(raw, dict):
            continue
        latitude, longitude = _coordinate(raw.get("lat")), _coordinate(raw.get("lon"))
        if latitude is None or longitude is None:
            continue
        address = raw.get("address") or {}
        name = raw.get("name") or next((address[k] for k in _NAME_KEYS if address.get(k)), None)
        if not name:
            continue
        region = address.get("state") or address.get("region") or None
        if (name, region) in seen:
            continue
        seen.add((name, region))
        places.append(
            WeatherPlace(
                name=str(name),
                region=str(region) if region else None,
                country_code=str(address.get("country_code") or "").upper(),
                latitude=latitude,
                longitude=longitude,
            )
        )
    return places
