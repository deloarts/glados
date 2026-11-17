"""
How a user wants dates rendered in the UI.

A closed set of presets rather than a locale tag or a free-form pattern. A
locale tag such as "en-US" would also bring month names, week start and
number formatting, and overlaps the separate `language` preference. A
free-form pattern would need a token validator and lets a user save
something unrenderable.

Presentation only. Timestamps are stored and transported as UTC ISO-8601
regardless of this setting, and every date-valued API parameter stays
`YYYY-MM-DD`. See the note in core/utils/dates.ts on the frontend side.

Time of day is deliberately not covered: it is always rendered 24-hour.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class DateFormat(StrValueEnum):
    ISO = "iso"  # 2026-08-06
    DMY_DOT = "dmy_dot"  # 06.08.2026
    DMY_SLASH = "dmy_slash"  # 06/08/2026
    MDY_SLASH = "mdy_slash"  # 08/06/2026
    D_MON_Y = "d_mon_y"  # 06 Aug 2026

    @classmethod
    def default(cls) -> "DateFormat":
        """ISO, matching the date format every date input in the UI already
        uses and the one the API itself speaks."""
        return cls.ISO
