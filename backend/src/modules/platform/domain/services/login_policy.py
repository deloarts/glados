"""Which login methods are currently permitted, and the 2FA and lockout
policy around them.

The system user is exempt from `allow_local_login`. Password login is the
only interactive method besides passkeys, which have to be set up with a
password first, so disabling it locks out most humans; signing in
as `system` (password from the deployment config) is the in-app way back,
and `admin enable-local-login` the CLI one. Because a way back always
exists, disabling local login is allowed rather than refused.
"""

from datetime import datetime
from datetime import timedelta

from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import LocalLoginDisabledError
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.permission import Permission


def assert_local_login_allowed(user: User, allow_local_login: bool) -> None:
    """Raises unless `user` may sign in with a password. Checked after the
    credentials, so it cannot be probed without a valid account."""
    if allow_local_login:
        return
    if user.is_systemuser:
        return
    raise LocalLoginDisabledError("Password login is currently disabled.")


def resolves_to_ldap(user: User, ldap_enabled: bool) -> bool:
    """Whether this user's password is checked against the directory.

    The `system` account is always local, matched by name rather than by
    `is_systemuser`, so a stray flag on another row could never reopen a
    directory bypass. It is the in-app way back when LDAP is misconfigured
    (`admin disable-ldap` is the CLI one), which is why the name is
    reserved. This only decides routing: with LDAP off, directory users
    still fail locally because their stored hash is unusable.
    """
    if user.username == SYSTEM_USER:
        return False
    return ldap_enabled and user.auth_provider == AuthProvider.LDAP


def totp_enrolment_required(user: User, *, enforce_totp: bool) -> bool:
    """Whether this user needs 2FA before getting a session: when
    `enforce_totp` is on, for write:settings holders, and always for the
    system user, which holds every permission. `admin reset-totp system`
    recovers a lost authenticator for it.
    """
    if user.is_systemuser:
        return True
    if enforce_totp:
        return True
    return user.has_permission(Permission.WRITE_SETTINGS)


def effective_trusted_device_days(user: User, configured_days: int) -> int:
    """How many days "trust this device" may skip 2FA. Always 0 for the
    system user, whose mandatory 2FA would otherwise be true in name only.
    """
    if user.is_systemuser:
        return 0
    return configured_days


# A passkey login never reaches the directory, so a directory account
# disabled there could keep signing in with its passkey. Asking for the
# password again after this many days bounds that window; deactivating the
# account in Glados, or removing its passkeys, closes it at once.
PASSKEY_DIRECTORY_RECHECK_DAYS = 30


def passkey_needs_password(user: User, *, ldap_enabled: bool, now: datetime) -> bool:
    """Whether a verified passkey login must still be refused until the user
    signs in with their password once. Only directory accounts are affected,
    since a local account's password lives here and cannot be revoked
    elsewhere."""
    if not resolves_to_ldap(user, ldap_enabled):
        return False
    if user.password_verified_at is None:
        return True
    return now - user.password_verified_at > timedelta(days=PASSKEY_DIRECTORY_RECHECK_DAYS)


# ── Password login throttle ──────────────────────────────────────────
#
# Failed password logins are throttled on three scopes. The address and
# the pair of username and address get hard locks, which only shut out the
# address that failed. The username alone gets a growing delay instead:
# a lock on it would let anyone who knows a username shut its owner out
# from everywhere, while a delay capped at a minute only slows the owner
# down and still costs an attacker spread over many addresses one guess
# per delay.

# Failed logins one address may make within one window, over every
# username, before it is locked. Fixed rather than a setting, like the TOTP
# throttle below, and high enough that many people behind one address can
# mistype their passwords now and then.
IP_MAX_FAILED_LOGINS = 30
IP_FAILURE_WINDOW_SECONDS = 60 * 60
IP_LOCK_SECONDS = 15 * 60

# The longest a username's growing delay can get.
USERNAME_DELAY_CAP_SECONDS = 60


def lockout_triggered(failure_count: int, max_login_attempts: int) -> bool:
    """Whether this many consecutive failures for one username from one
    address lock that pair. 0 means unlimited."""
    if max_login_attempts <= 0:
        return False
    return failure_count >= max_login_attempts


def lockout_seconds(lockout_duration_minutes: int) -> int:
    """How long a lock lasts. Guards against a 0/negative setting turning
    the lock into a no-op that still resets the counter."""
    return max(lockout_duration_minutes, 1) * 60


def ip_lockout_triggered(failure_count: int) -> bool:
    """Whether this many failed logins from one address within one window
    lock the address for IP_LOCK_SECONDS."""
    return failure_count >= IP_MAX_FAILED_LOGINS


def ip_failure_window(epoch_seconds: float) -> int:
    """The number of the fixed window an address's failures are counted
    in, so the count starts over every IP_FAILURE_WINDOW_SECONDS."""
    return int(epoch_seconds // IP_FAILURE_WINDOW_SECONDS)


def username_delay_seconds(failure_count: int, max_login_attempts: int) -> int:
    """How long a username must wait before its next password attempt after
    this many failures from any address. Nothing below the limit; from the
    limit on one second, doubling with every further failure up to
    USERNAME_DELAY_CAP_SECONDS. 0 means unlimited, so no delay either."""
    if max_login_attempts <= 0 or failure_count < max_login_attempts:
        return 0
    exponent = min(failure_count - max_login_attempts, 16)
    return int(min(2**exponent, USERNAME_DELAY_CAP_SECONDS))


# ── TOTP step throttle ───────────────────────────────────────────────
#
# Fixed, unlike password lockout: a 6-digit code is only safe while guessing
# is slow. Only login_totp needs it, because it is reachable with just a
# stolen password; the other TOTP paths require a live session.

TOTP_MAX_ATTEMPTS = 5
TOTP_LOCK_SECONDS = 300


def totp_lockout_triggered(failure_count: int) -> bool:
    """Whether this many consecutive wrong/replayed codes should lock the
    partial-token holder out of further attempts for TOTP_LOCK_SECONDS."""
    return failure_count >= TOTP_MAX_ATTEMPTS
