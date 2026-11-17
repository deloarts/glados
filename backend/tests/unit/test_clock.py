"""
Unit tests for the clock service (src/shared_kernel/domain/services/clock.py), which
centralises "now" so every timestamp the app stores is UTC regardless of
the host's local timezone.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.services.clock import today_utc


class TestNowUtc:
    def test_returns_a_datetime(self):
        assert isinstance(now_utc(), datetime)

    def test_is_timezone_aware_with_utc_tzinfo(self):
        result = now_utc()
        assert result.tzinfo is not None
        assert result.tzinfo == UTC
        assert result.utcoffset().total_seconds() == 0


class TestTodayUtc:
    def test_returns_a_date(self):
        result = today_utc()
        assert isinstance(result, date)
        assert not isinstance(result, datetime)

    def test_equals_now_utc_date(self):
        assert today_utc() == now_utc().date()


class TestAsUtc:
    def test_as_utc_reads_a_naive_value_as_utc(self):
        assert as_utc(datetime(2026, 1, 1, 8, 0)) == datetime(2026, 1, 1, 8, 0, tzinfo=UTC)

    def test_as_utc_converts_an_aware_value_to_utc(self):
        vienna_winter = timezone(timedelta(hours=1))
        result = as_utc(datetime(2026, 1, 1, 9, 0, tzinfo=vienna_winter))
        assert result == datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        assert result.tzinfo == UTC

    def test_as_utc_stays_importable_from_the_scheduling_package(self):
        from src.modules.fulfillment.domain.services import scheduling

        assert scheduling.as_utc is as_utc
