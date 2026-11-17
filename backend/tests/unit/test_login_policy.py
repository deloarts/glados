"""
Direct tests for assert_local_login_allowed.

The system-user exemption is the load-bearing part: password login is
currently the only interactive method, so removing that branch would turn
"disable local login" into an unrecoverable, application-wide lockout.
"""

from typing import Any

import pytest

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import LocalLoginDisabledError
from src.modules.platform.domain.services.login_policy import TOTP_MAX_ATTEMPTS
from src.modules.platform.domain.services.login_policy import assert_local_login_allowed
from src.modules.platform.domain.services.login_policy import effective_trusted_device_days
from src.modules.platform.domain.services.login_policy import lockout_seconds
from src.modules.platform.domain.services.login_policy import lockout_triggered
from src.modules.platform.domain.services.login_policy import resolves_to_ldap
from src.modules.platform.domain.services.login_policy import totp_enrolment_required
from src.modules.platform.domain.services.login_policy import totp_lockout_triggered
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories


def make_user(
    *, is_systemuser: bool = False, username: str | None = None, **overrides: Any
) -> User:
    """A user named `system` when flagged as the system user, as the real one is."""
    if username is None:
        username = "system" if is_systemuser else "tester"
    return factories.make_user(username=username, is_systemuser=is_systemuser, **overrides)


class TestAssertLocalLoginAllowed:
    def test_enabled_allows_an_ordinary_user(self):
        assert_local_login_allowed(make_user(), allow_local_login=True)

    def test_disabled_rejects_an_ordinary_user(self):
        with pytest.raises(LocalLoginDisabledError):
            assert_local_login_allowed(make_user(), allow_local_login=False)

    def test_disabled_still_allows_the_system_user(self):
        assert_local_login_allowed(make_user(is_systemuser=True), allow_local_login=False)

    def test_enabled_allows_the_system_user_too(self):
        assert_local_login_allowed(make_user(is_systemuser=True), allow_local_login=True)

    def test_the_exemption_is_the_only_way_through_when_disabled(self):
        """Pins the recovery path: if this ever narrows, disabling the
        setting becomes an unrecoverable lockout."""
        with pytest.raises(LocalLoginDisabledError):
            assert_local_login_allowed(make_user(is_systemuser=False), allow_local_login=False)

        assert_local_login_allowed(make_user(is_systemuser=True), allow_local_login=False)


class TestTotpEnrolmentRequired:
    def test_not_required_for_an_ordinary_user_when_not_enforced(self):
        assert totp_enrolment_required(make_user(), enforce_totp=False) is False

    def test_required_for_everyone_when_enforced(self):
        assert totp_enrolment_required(make_user(), enforce_totp=True) is True

    def test_required_for_write_settings_holders_even_without_enforcement(self):
        """An account that can rewrite security policy, mint users and
        reach storage config warrants a second factor regardless."""
        admin = make_user(permissions=[Permission.WRITE_SETTINGS])

        assert totp_enrolment_required(admin, enforce_totp=False) is True

    def test_not_required_for_other_permissions(self):
        writer = make_user(permissions=[Permission.WRITE_PROJECTS])

        assert totp_enrolment_required(writer, enforce_totp=False) is False


class TestSystemUserTotpIsMandatory:
    """The account that carries every permission (User.has_permission
    shortcuts to True for all of them when is_systemuser) is not exempt
    from 2FA, since an exemption would make it the weakest link in the
    whole account, not a safety valve. `admin reset-totp system` (CLI) is
    the recovery path, forcing re-enrolment on the next login.
    """

    def test_required_even_without_enforcement(self):
        assert totp_enrolment_required(make_user(is_systemuser=True), enforce_totp=False) is True

    def test_required_when_enforced_globally_too(self):
        assert totp_enrolment_required(make_user(is_systemuser=True), enforce_totp=True) is True

    def test_checked_before_the_implicit_write_settings_permission(self):
        """Pins the ordering, not just the outcome: has_permission would
        also answer True here, so this must not be an accident of testing
        the permission branch first."""
        system = make_user(is_systemuser=True)
        assert system.has_permission(Permission.WRITE_SETTINGS) is True

        assert totp_enrolment_required(system, enforce_totp=False) is True

    def test_the_two_recovery_paths_no_longer_agree(self):
        """Deliberately: password login stays reachable with config alone
        (allow_local_login's exemption), but 2FA is mandatory even for
        the system user, the CLI is its only reset path."""
        system = make_user(is_systemuser=True)

        assert_local_login_allowed(system, allow_local_login=False)
        assert totp_enrolment_required(system, enforce_totp=True) is True


class TestEffectiveTrustedDeviceDays:
    """The "trust this device" feature must not degrade mandatory 2FA into
    "2FA once every N days" for the system user."""

    def test_ordinary_user_gets_the_configured_value(self):
        assert effective_trusted_device_days(make_user(), 30) == 30

    def test_system_user_always_gets_zero(self):
        assert effective_trusted_device_days(make_user(is_systemuser=True), 30) == 0

    def test_system_user_gets_zero_even_when_the_setting_is_already_zero(self):
        assert effective_trusted_device_days(make_user(is_systemuser=True), 0) == 0

    def test_ordinary_user_with_the_feature_off_gets_zero_too(self):
        assert effective_trusted_device_days(make_user(), 0) == 0


class TestResolvesToLdap:
    """Which credential store answers for a user."""

    def test_ldap_user_resolves_to_ldap(self):
        user = make_user(auth_provider=AuthProvider.LDAP)
        assert resolves_to_ldap(user, ldap_enabled=True) is True

    def test_local_user_stays_local(self):
        user = make_user(auth_provider=AuthProvider.LOCAL)
        assert resolves_to_ldap(user, ldap_enabled=True) is False

    def test_global_switch_off_forces_local(self):
        user = make_user(auth_provider=AuthProvider.LDAP)
        assert resolves_to_ldap(user, ldap_enabled=False) is False

    def test_system_user_is_never_routed_to_the_directory(self):
        """The break-glass identity. If this regressed, enabling LDAP against
        a misconfigured server would lock out the one account that can turn
        it off again."""
        user = make_user(is_systemuser=True, auth_provider=AuthProvider.LDAP)
        assert resolves_to_ldap(user, ldap_enabled=True) is False

    def test_exemption_is_by_name_not_by_the_systemuser_flag(self):
        """is_systemuser can be granted to other accounts, so a flag-based
        exemption would let every promoted superuser bypass the directory."""
        promoted = make_user(username="alice", is_systemuser=True, auth_provider=AuthProvider.LDAP)
        assert promoted.is_systemuser is True
        assert resolves_to_ldap(promoted, ldap_enabled=True) is True

    def test_an_account_merely_named_system_is_exempt(self):
        """The corollary, and why `system` must be a reserved username."""
        impostor = make_user(username="system", auth_provider=AuthProvider.LDAP)
        assert impostor.is_systemuser is False
        assert resolves_to_ldap(impostor, ldap_enabled=True) is False


class TestLockoutPolicy:
    """Direct coverage of the lockout rules, which the AD badPwdCount
    protection depends on."""

    def test_zero_max_attempts_never_locks(self):
        assert lockout_triggered(99, 0) is False

    def test_zero_remains_an_explicit_opt_out(self):
        """The shipped default is 5, so 0 is the explicit opt-out rather
        than the shipped value: it never locks, at any failure count."""
        assert lockout_triggered(9999, 0) is False

    def test_negative_max_attempts_never_locks(self):
        assert lockout_triggered(99, -1) is False

    def test_locks_once_the_limit_is_reached(self):
        assert lockout_triggered(3, 3) is True

    def test_does_not_lock_below_the_limit(self):
        assert lockout_triggered(2, 3) is False

    def test_lockout_duration_is_converted_to_seconds(self):
        assert lockout_seconds(15) == 900

    def test_zero_duration_still_locks_for_a_minute(self):
        """Otherwise the lock would be a no-op that still cleared the
        counter, making the setting silently worse than useless."""
        assert lockout_seconds(0) == 60
        assert lockout_seconds(-5) == 60


class TestTotpLockoutPolicy:
    """Unlike password lockout above, these are fixed constants, not an
    admin setting, see login_policy.py's TOTP-throttle section for why."""

    def test_locks_once_the_limit_is_reached(self):
        assert totp_lockout_triggered(TOTP_MAX_ATTEMPTS) is True

    def test_does_not_lock_below_the_limit(self):
        assert totp_lockout_triggered(TOTP_MAX_ATTEMPTS - 1) is False

    def test_keeps_locking_past_the_limit(self):
        """A stale/overshooting count (e.g. a race between two concurrent
        requests) must not un-trip the lock."""
        assert totp_lockout_triggered(TOTP_MAX_ATTEMPTS + 5) is True
