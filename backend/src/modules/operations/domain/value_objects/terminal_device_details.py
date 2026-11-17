"""The hardware details a terminal reports about itself: the computer the
bridge runs on and the display attached to it.

Every value comes from the device and is untrusted. `parse_device_details`
therefore never refuses a report: text loses control characters and is cut
to its cap, a number outside its plausible range or of the wrong type is
dropped, and anything unknown is ignored. A display that reports nonsense
still signs in; it only shows less on the terminals tab.

The serials and the hostname identify one device and are only shown to
holders of manage:terminals.
"""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import fields
from typing import Any
from typing import Final

SHORT_TEXT_MAX: Final = 64
TEXT_MAX: Final = 200
HOSTNAME_MAX: Final = 253

_RAM_MB_MAX: Final = 1_048_576
_TEMPERATURE_RANGE: Final = (-55.0, 150.0)
_UPTIME_SECONDS_MAX: Final = 10 * 365 * 24 * 3600
_PIXELS_MAX: Final = 100_000
_MILLIMETRES_MAX: Final = 10_000


@dataclass(frozen=True)
class TerminalDeviceDetails:
    # ── Computer ──────────────────────────────────────────────────────
    computer_model: str | None = None
    computer_serial: str | None = None
    ram_mb: int | None = None
    cpu_temperature_c: float | None = None
    uptime_seconds: int | None = None
    kernel: str | None = None
    os_name: str | None = None
    hostname: str | None = None
    under_voltage: bool | None = None
    throttled: bool | None = None

    # ── Display ───────────────────────────────────────────────────────
    display_make: str | None = None
    display_model: str | None = None
    display_serial: str | None = None
    display_width_px: int | None = None
    display_height_px: int | None = None
    display_width_mm: int | None = None
    display_height_mm: int | None = None
    display_connector: str | None = None
    display_connected: bool | None = None
    display_power_state: str | None = None
    cec_available: bool | None = None

    def without_identifiers(self) -> "TerminalDeviceDetails":
        """The details with the serials and the hostname left out, for a
        reader without manage:terminals."""
        return TerminalDeviceDetails(
            **{
                f.name: None if f.name in IDENTIFYING_FIELDS else getattr(self, f.name)
                for f in fields(self)
            }
        )


# Fields that identify one device; only manage:terminals sees them.
IDENTIFYING_FIELDS: Final = frozenset({"computer_serial", "display_serial", "hostname"})

_TEXT_CAPS: Final[dict[str, int]] = {
    "computer_model": TEXT_MAX,
    "computer_serial": SHORT_TEXT_MAX,
    "kernel": TEXT_MAX,
    "os_name": TEXT_MAX,
    "hostname": HOSTNAME_MAX,
    "display_make": SHORT_TEXT_MAX,
    "display_model": TEXT_MAX,
    "display_serial": SHORT_TEXT_MAX,
    "display_connector": SHORT_TEXT_MAX,
    "display_power_state": SHORT_TEXT_MAX,
}
_INT_RANGES: Final[dict[str, tuple[int, int]]] = {
    "ram_mb": (1, _RAM_MB_MAX),
    "uptime_seconds": (0, _UPTIME_SECONDS_MAX),
    "display_width_px": (1, _PIXELS_MAX),
    "display_height_px": (1, _PIXELS_MAX),
    "display_width_mm": (1, _MILLIMETRES_MAX),
    "display_height_mm": (1, _MILLIMETRES_MAX),
}
_BOOLS: Final = frozenset({"under_voltage", "throttled", "display_connected", "cec_available"})


def _text(value: Any, cap: int) -> str | None:
    if not isinstance(value, str):
        return None
    # Whitespace runs, line breaks included, become one space before the
    # remaining control and format characters are dropped.
    cleaned = " ".join(value.split())
    cleaned = "".join(ch for ch in cleaned if not unicodedata.category(ch).startswith("C"))
    cleaned = cleaned[:cap].strip()
    return cleaned or None


def _int(value: Any, bounds: tuple[int, int]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    low, high = bounds
    number = int(value)
    return number if low <= number <= high else None


def _temperature(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    low, high = _TEMPERATURE_RANGE
    return round(float(value), 1) if low <= value <= high else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def parse_device_details(raw: Mapping[str, Any]) -> TerminalDeviceDetails:
    """The details of a report, cleaned. Never raises on a value."""
    values: dict[str, Any] = {}
    for name, cap in _TEXT_CAPS.items():
        values[name] = _text(raw.get(name), cap)
    for name, bounds in _INT_RANGES.items():
        values[name] = _int(raw.get(name), bounds)
    for name in _BOOLS:
        values[name] = _bool(raw.get(name))
    values["cpu_temperature_c"] = _temperature(raw.get("cpu_temperature_c"))
    return TerminalDeviceDetails(**values)


def device_details_to_data(details: TerminalDeviceDetails) -> dict[str, Any]:
    """Plain data of every field, the shape parse_device_details reads."""
    return {f.name: getattr(details, f.name) for f in fields(details)}
