"""
Unit tests for src.modules.platform.domain.services.datetime_filters: resolve_actor_timezone's
fallback behavior and expand_date_filter's date-only whole-day expansion
and datetime passthrough. No database, no HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.platform.domain.services.datetime_filters import expand_date_filter
from src.modules.platform.domain.services.datetime_filters import resolve_actor_timezone

VIENNA = ZoneInfo("Europe/Vienna")

# ── resolve_actor_timezone ──────────────────────────────────────────────


class TestResolveActorTimezone:
    def test_resolves_a_known_iana_name(self):
        assert resolve_actor_timezone("Europe/Vienna") == ZoneInfo("Europe/Vienna")

    def test_falls_back_to_utc_for_an_unknown_name(self):
        assert resolve_actor_timezone("Not/A_Real_Zone") == ZoneInfo("UTC")

    def test_falls_back_to_utc_for_an_empty_string(self):
        assert resolve_actor_timezone("") == ZoneInfo("UTC")


# ── expand_date_filter: datetime passthrough ────────────────────────────


class TestExpandDateFilterWithDatetime:
    def test_tz_aware_datetime_is_returned_unchanged(self):
        value = datetime(2026, 6, 15, 8, 30, tzinfo=UTC)
        assert expand_date_filter(value, VIENNA, end_of_day=False) == value

    def test_tz_aware_non_utc_datetime_is_returned_unchanged(self):
        value = datetime(2026, 6, 15, 8, 30, tzinfo=ZoneInfo("Europe/Vienna"))
        assert expand_date_filter(value, UTC, end_of_day=True) == value

    def test_naive_datetime_is_treated_as_utc(self):
        value = datetime(2026, 6, 15, 8, 30)
        result = expand_date_filter(value, VIENNA, end_of_day=False)
        assert result == datetime(2026, 6, 15, 8, 30, tzinfo=UTC)

    def test_end_of_day_flag_is_irrelevant_once_a_time_is_already_present(self):
        value = datetime(2026, 6, 15, 8, 30, tzinfo=UTC)
        assert expand_date_filter(value, UTC, end_of_day=True) == value


# ── expand_date_filter: date-only whole-day expansion ───────────────────


class TestExpandDateFilterWithDateOnly:
    def test_start_of_day_in_utc(self):
        result = expand_date_filter(date(2026, 6, 15), UTC, end_of_day=False)
        assert result == datetime(2026, 6, 15, 0, 0, 0, tzinfo=UTC)

    def test_end_of_day_in_utc(self):
        result = expand_date_filter(date(2026, 6, 15), UTC, end_of_day=True)
        assert result.date() == date(2026, 6, 15)
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.tzinfo == UTC

    def test_start_of_day_in_a_summer_offset_zone_converts_to_the_prior_utc_day(self):
        # Europe/Vienna is UTC+2 in June (CEST): 2026-06-15 00:00 local is
        # 2026-06-14 22:00 UTC.
        result = expand_date_filter(date(2026, 6, 15), VIENNA, end_of_day=False)
        assert result == datetime(2026, 6, 14, 22, 0, 0, tzinfo=UTC)

    def test_end_of_day_in_a_summer_offset_zone_converts_to_the_same_utc_day(self):
        # 2026-06-15 23:59:59.999999 CEST (UTC+2) is 2026-06-15 21:59:59.999999 UTC.
        result = expand_date_filter(date(2026, 6, 15), VIENNA, end_of_day=True)
        assert result == datetime(2026, 6, 15, 21, 59, 59, 999999, tzinfo=UTC)

    def test_start_and_end_of_day_bracket_the_whole_calendar_day(self):
        start = expand_date_filter(date(2026, 6, 15), VIENNA, end_of_day=False)
        end = expand_date_filter(date(2026, 6, 15), VIENNA, end_of_day=True)
        assert start < end
        assert (end - start).total_seconds() < 24 * 60 * 60
        assert (end - start).total_seconds() > 24 * 60 * 60 - 1

    def test_unknown_timezone_falls_back_to_utc_day_boundaries(self):
        zone = resolve_actor_timezone("Not/A_Real_Zone")
        result = expand_date_filter(date(2026, 6, 15), zone, end_of_day=False)
        assert result == datetime(2026, 6, 15, 0, 0, 0, tzinfo=UTC)

    def test_result_is_always_tz_aware(self):
        result = expand_date_filter(date(2026, 6, 15), VIENNA, end_of_day=False)
        assert result.tzinfo is not None
