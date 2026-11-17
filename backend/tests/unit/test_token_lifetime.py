"""
The lifetime cap on new tokens (domain/services/token_lifetime.py): while
`token_max_lifetime_days` is above 0 every new token needs an expiry within
it, and 0 lifts the cap.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.platform.domain.exceptions import TokenExpiryRequiredError
from src.modules.platform.domain.exceptions import TokenLifetimeExceededError
from src.modules.platform.domain.services.token_lifetime import assert_expiry_date_allowed
from src.modules.platform.domain.services.token_lifetime import assert_lifetime_days_allowed

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


class TestLifetimeDays:
    def test_no_expiry_is_refused_while_capped(self):
        with pytest.raises(TokenExpiryRequiredError):
            assert_lifetime_days_allowed(None, 30)

    def test_the_cap_itself_is_allowed(self):
        assert_lifetime_days_allowed(30, 30)

    def test_beyond_the_cap_is_refused(self):
        with pytest.raises(TokenLifetimeExceededError):
            assert_lifetime_days_allowed(31, 30)

    def test_zero_lifts_the_cap(self):
        assert_lifetime_days_allowed(None, 0)
        assert_lifetime_days_allowed(36500, 0)


class TestExpiryDate:
    def test_no_expiry_date_is_refused_while_capped(self):
        with pytest.raises(TokenExpiryRequiredError):
            assert_expiry_date_allowed(None, NOW, 30)

    def test_a_date_within_the_cap_is_allowed(self):
        assert_expiry_date_allowed(NOW + timedelta(days=29, hours=23), NOW, 30)

    def test_the_full_cap_is_refused(self):
        with pytest.raises(TokenLifetimeExceededError):
            assert_expiry_date_allowed(NOW + timedelta(days=30), NOW, 30)

    def test_zero_lifts_the_cap(self):
        assert_expiry_date_allowed(None, NOW, 0)
        assert_expiry_date_allowed(NOW + timedelta(days=5000), NOW, 0)
