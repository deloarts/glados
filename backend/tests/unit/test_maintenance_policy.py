"""
Direct tests for maintenance_policy.py.

The system-user exemption is the load-bearing part, same as
test_login_policy.py's: whatever else is misconfigured (the allowlist
emptied by mistake, write:settings revoked from every remaining admin),
`system` must always be the way back in.
"""

from typing import Any

import pytest

from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.services.maintenance_policy import DEFAULT_MESSAGE
from src.modules.platform.domain.services.maintenance_policy import assert_maintenance_allows
from src.modules.platform.domain.services.maintenance_policy import ip_is_allowed
from src.modules.platform.domain.services.maintenance_policy import is_exempt
from src.modules.platform.domain.services.maintenance_policy import normalise_allowed_ips
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories


def make_user(
    *, is_systemuser: bool = False, username: str | None = None, **overrides: Any
) -> User:
    """A user named `system` when flagged as the system user, as the real one is."""
    if username is None:
        username = "system" if is_systemuser else "tester"
    return factories.make_user(username=username, is_systemuser=is_systemuser, **overrides)


def make_settings(
    *, enabled: bool = True, message: str | None = None, allowed_ips: list[str] | None = None
) -> AdminMaintenanceSettings:
    return AdminMaintenanceSettings(
        id=1, enabled=enabled, message=message, allowed_ips=allowed_ips or []
    )


class TestNormaliseAllowedIps:
    def test_strips_whitespace(self):
        assert normalise_allowed_ips([" 10.0.0.1 "]) == ["10.0.0.1"]

    def test_drops_empty_entries(self):
        assert normalise_allowed_ips(["10.0.0.1", "", "   "]) == ["10.0.0.1"]

    def test_deduplicates_preserving_order(self):
        assert normalise_allowed_ips(["10.0.0.2", "10.0.0.1", "10.0.0.2"]) == [
            "10.0.0.2",
            "10.0.0.1",
        ]

    def test_dedupes_after_trimming(self):
        """A duplicate hidden by whitespace must still collapse to one."""
        assert normalise_allowed_ips(["10.0.0.1", " 10.0.0.1 "]) == ["10.0.0.1"]

    def test_accepts_a_cidr_network(self):
        assert normalise_allowed_ips(["10.0.0.0/8"]) == ["10.0.0.0/8"]

    def test_accepts_an_ipv6_address(self):
        assert normalise_allowed_ips(["::1"]) == ["::1"]

    def test_accepts_an_ipv6_network(self):
        assert normalise_allowed_ips(["2001:db8::/32"]) == ["2001:db8::/32"]

    def test_rejects_an_invalid_entry(self):
        with pytest.raises(ValueError, match="not-an-ip"):
            normalise_allowed_ips(["10.0.0.1", "not-an-ip"])

    def test_empty_list_stays_empty(self):
        assert normalise_allowed_ips([]) == []


class TestIpIsAllowed:
    def test_exact_match(self):
        assert ip_is_allowed("10.0.0.1", ["10.0.0.1"]) is True

    def test_non_member(self):
        assert ip_is_allowed("10.0.0.2", ["10.0.0.1"]) is False

    def test_member_of_a_cidr_network(self):
        assert ip_is_allowed("10.1.2.3", ["10.1.0.0/16"]) is True

    def test_outside_a_cidr_network(self):
        assert ip_is_allowed("10.2.0.1", ["10.1.0.0/16"]) is False

    def test_none_client_ip_is_never_allowed(self):
        assert ip_is_allowed(None, ["0.0.0.0/0"]) is False

    def test_garbage_client_ip_is_never_allowed(self):
        assert ip_is_allowed("not-an-ip", ["10.0.0.1"]) is False

    def test_a_garbage_stored_entry_is_skipped_not_raised(self):
        """normalise_allowed_ips already rejects bad entries on the way in,
        but a row written before that validation existed (or edited
        directly in the database) must not blow up a live request."""
        assert ip_is_allowed("10.0.0.1", ["garbage", "10.0.0.1"]) is True

    def test_empty_allowlist_allows_nothing(self):
        assert ip_is_allowed("10.0.0.1", []) is False


class TestIsExempt:
    def test_system_user_is_always_exempt(self):
        user = make_user(is_systemuser=True)
        settings = make_settings(allowed_ips=[])
        assert is_exempt(user, settings, client_ip=None) is True

    def test_write_settings_holder_is_exempt(self):
        user = make_user(permissions=[Permission.WRITE_SETTINGS])
        settings = make_settings()
        assert is_exempt(user, settings, client_ip=None) is True

    def test_allowlisted_ip_is_exempt(self):
        user = make_user()
        settings = make_settings(allowed_ips=["10.0.0.1"])
        assert is_exempt(user, settings, client_ip="10.0.0.1") is True

    def test_plain_user_from_an_unlisted_ip_is_not_exempt(self):
        user = make_user()
        settings = make_settings(allowed_ips=["10.0.0.1"])
        assert is_exempt(user, settings, client_ip="10.0.0.2") is False

    def test_plain_user_with_no_client_ip_is_not_exempt(self):
        user = make_user()
        settings = make_settings()
        assert is_exempt(user, settings, client_ip=None) is False


class TestAssertMaintenanceAllows:
    def test_disabled_is_a_no_op_for_anyone(self):
        assert_maintenance_allows(make_user(), make_settings(enabled=False), client_ip=None)

    def test_enabled_allows_an_exempt_user(self):
        assert_maintenance_allows(
            make_user(is_systemuser=True), make_settings(enabled=True), client_ip=None
        )

    def test_enabled_raises_for_a_plain_user(self):
        with pytest.raises(MaintenanceModeError):
            assert_maintenance_allows(make_user(), make_settings(enabled=True), client_ip=None)

    def test_raises_with_the_admin_configured_message(self):
        settings = make_settings(enabled=True, message="Back in 10 minutes.")
        with pytest.raises(MaintenanceModeError, match=r"Back in 10 minutes\."):
            assert_maintenance_allows(make_user(), settings, client_ip=None)

    def test_a_null_message_falls_back_to_the_default(self):
        settings = make_settings(enabled=True, message=None)
        with pytest.raises(MaintenanceModeError, match=DEFAULT_MESSAGE):
            assert_maintenance_allows(make_user(), settings, client_ip=None)

    def test_the_exemption_is_the_only_way_through_when_enabled(self):
        """Pins the recovery path the same way
        test_login_policy.py's equivalent test does: if this ever
        narrows, enabling maintenance mode becomes an unrecoverable
        lockout."""
        settings = make_settings(enabled=True)
        with pytest.raises(MaintenanceModeError):
            assert_maintenance_allows(make_user(is_systemuser=False), settings, client_ip=None)

        assert_maintenance_allows(make_user(is_systemuser=True), settings, client_ip=None)
