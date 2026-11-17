"""
The tenant's timezone, as an IANA name (e.g. "Europe/Vienna"), set as the
default timezone of the general settings. It is the one timezone the whole
app reads calendar days and wall-clock times in.

Not an Enum like Language/Theme: the valid set is the tz database shipped
with the platform, which is far too large to enumerate by hand and changes
between releases. Validation therefore asks `zoneinfo` at call time.

Storage is always UTC, this value only decides which wall clock a stored
instant is read against.
"""

from zoneinfo import available_timezones

from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE


class Timezone:
    @staticmethod
    def default() -> str:
        return SERVER_DEFAULT_TIMEZONE

    @staticmethod
    def is_valid(value: str) -> bool:
        return value in available_timezones()

    @staticmethod
    def values() -> list[str]:
        return sorted(available_timezones())
