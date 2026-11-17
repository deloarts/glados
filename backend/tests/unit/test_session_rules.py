"""
Direct tests for the idle and absolute expiry rules that decide when a
server-side session is over, and the last_seen write throttle.

The settings refuse an idle timeout of 0, but a value stored before that
rule still means no idle expiry rather than expiring at once; the absolute
lifetime bounds such a session anyway.
"""

from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.platform.domain.services.session_rules import DEFAULT_SESSION_MAX_LIFETIME_DAYS
from src.modules.platform.domain.services.session_rules import LAST_SEEN_WRITE_INTERVAL_SECONDS
from src.modules.platform.domain.services.session_rules import SYSTEM_USER_SESSION_LIFETIME_MINUTES
from src.modules.platform.domain.services.session_rules import last_activity
from src.modules.platform.domain.services.session_rules import last_seen_touch_due
from src.modules.platform.domain.services.session_rules import session_expired
from src.modules.platform.domain.services.session_rules import session_hard_expired
from src.modules.platform.domain.services.session_rules import session_hard_expiry

NOW = datetime(2026, 8, 10, 12, 0, 0)


class TestSessionExpired:
    def test_a_session_seen_within_the_timeout_is_alive(self):
        assert session_expired(NOW - timedelta(minutes=10), 30, NOW) is False

    def test_a_session_idle_past_the_timeout_is_expired(self):
        assert session_expired(NOW - timedelta(minutes=31), 30, NOW) is True

    def test_exactly_at_the_boundary_is_still_alive(self):
        """Strictly-greater comparison: the very last second belongs to
        the session."""
        assert session_expired(NOW - timedelta(minutes=30), 30, NOW) is False

    def test_zero_means_never_expires(self):
        assert session_expired(NOW - timedelta(days=365), 0, NOW) is False

    @pytest.mark.parametrize("value", [-1, -60])
    def test_negative_values_never_expire_rather_than_expiring_instantly(self, value):
        assert session_expired(NOW - timedelta(minutes=1), value, NOW) is False

    def test_one_minute_is_honoured(self):
        """A very short but positive timeout is a legitimate choice."""
        assert session_expired(NOW - timedelta(minutes=2), 1, NOW) is True
        assert session_expired(NOW - timedelta(seconds=30), 1, NOW) is False

    def test_large_values_are_honoured(self):
        assert session_expired(NOW - timedelta(days=6), 10_080, NOW) is False
        assert session_expired(NOW - timedelta(days=8), 10_080, NOW) is True


class TestSessionHardExpiry:
    """The absolute session lifetime (the row-level half), on top of the
    idle rule above, not a substitute for it."""

    def test_system_user_expiry_is_fifteen_minutes_after_creation(self):
        created = NOW - timedelta(minutes=5)
        assert session_hard_expiry(
            created, is_systemuser=True, max_lifetime_days=30
        ) == created + timedelta(minutes=SYSTEM_USER_SESSION_LIFETIME_MINUTES)

    def test_other_users_expire_after_the_configured_days(self):
        assert session_hard_expiry(NOW, is_systemuser=False, max_lifetime_days=7) == NOW + (
            timedelta(days=7)
        )

    @pytest.mark.parametrize("value", [0, -1])
    def test_a_non_positive_setting_falls_back_to_the_default(self, value):
        assert session_hard_expiry(
            NOW, is_systemuser=False, max_lifetime_days=value
        ) == NOW + timedelta(days=DEFAULT_SESSION_MAX_LIFETIME_DAYS)


class TestSessionHardExpired:
    def test_system_user_within_lifetime_is_not_expired(self):
        created = NOW - timedelta(minutes=10)
        assert session_hard_expired(created, True, NOW, 30) is False

    def test_system_user_past_lifetime_is_expired(self):
        created = NOW - timedelta(minutes=16)
        assert session_hard_expired(created, True, NOW, 30) is True

    def test_exactly_at_the_boundary_is_still_alive(self):
        """Strictly-greater comparison, same convention as session_expired
        above: the very last second belongs to the session."""
        created = NOW - timedelta(minutes=SYSTEM_USER_SESSION_LIFETIME_MINUTES)
        assert session_hard_expired(created, True, NOW, 30) is False

    def test_one_second_past_the_boundary_is_expired(self):
        created = NOW - timedelta(minutes=SYSTEM_USER_SESSION_LIFETIME_MINUTES, seconds=1)
        assert session_hard_expired(created, True, NOW, 30) is True

    def test_other_users_live_until_the_configured_lifetime(self):
        assert session_hard_expired(NOW - timedelta(days=29), False, NOW, 30) is False
        assert session_hard_expired(NOW - timedelta(days=30, seconds=1), False, NOW, 30) is True

    def test_activity_does_not_extend_the_lifetime(self):
        """Unlike the idle timeout, the absolute lifetime counts from sign-in
        only, so a session in constant use still ends."""
        created = NOW - timedelta(days=31)
        assert session_expired(NOW, 1440, NOW) is False
        assert session_hard_expired(created, False, NOW, 30) is True


class TestLastSeenTouchDue:
    def test_a_fresh_timestamp_is_not_rewritten(self):
        assert last_seen_touch_due(NOW - timedelta(seconds=5), NOW) is False

    def test_a_stale_timestamp_is_rewritten(self):
        assert (
            last_seen_touch_due(NOW - timedelta(seconds=LAST_SEEN_WRITE_INTERVAL_SECONDS + 1), NOW)
            is True
        )

    def test_the_throttle_is_short_enough_to_keep_idle_expiry_accurate(self):
        """The throttle bounds how much idle time can go unrecorded; it
        must stay far below any plausible timeout (minutes-granularity)."""
        assert 0 < LAST_SEEN_WRITE_INTERVAL_SECONDS <= 60


class TestLastActivity:
    def test_a_request_without_a_report_is_activity_itself(self):
        assert last_activity(NOW, None) == NOW

    def test_a_report_dates_the_activity_back(self):
        assert last_activity(NOW, 90) == NOW - timedelta(seconds=90)

    def test_a_negative_report_counts_as_none(self):
        assert last_activity(NOW, -5) == NOW
