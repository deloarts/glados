"""
The throttle in front of every password check: the password login and the
password confirmations on the caller's own account (passkey registration,
changing the own password). One instance per request, over the shared
ILoginAttemptTracker.

It keeps three scopes, with the policy in domain/services/login_policy.py:

- the client address, `ip:{address}`, locked after too many failures within
  one window whatever the username;
- the username on one address, `{username}|{address}`, locked after
  `max_login_attempts` failures for `lockout_duration_minutes`;
- the username alone, counted under the bare username, which earns a
  growing delay held as the lock `delay:{username}`. A delay rather than a
  lock, so nobody can shut a user out from every address by failing on
  purpose.

A request without a known address skips the address scope and counts the
pair under `unknown`. A failure reports the scopes it locked or started
delaying, so the caller can record each in the security log once rather
than every refused attempt. A success clears the username's counter, its delay
and its pair on that address, never the address scope, so one valid account
cannot be used to reset an address's budget.
"""

from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.domain.services.login_policy import IP_LOCK_SECONDS
from src.modules.platform.domain.services.login_policy import ip_failure_window
from src.modules.platform.domain.services.login_policy import ip_lockout_triggered
from src.modules.platform.domain.services.login_policy import lockout_seconds
from src.modules.platform.domain.services.login_policy import lockout_triggered
from src.modules.platform.domain.services.login_policy import username_delay_seconds
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.shared_kernel.domain.services.clock import now_utc

LOCKED_MESSAGE = "Too many failed attempts. Try again later."

_UNKNOWN_ADDRESS = "unknown"

# The scope names a failure reports when it locks or delays a scope.
SCOPE_ADDRESS = "address"
SCOPE_ACCOUNT_ON_ADDRESS = "account_on_address"
SCOPE_ACCOUNT = "account"


def normalise_username(username: str) -> str:
    """The throttle's spelling of a username or e-mail. Active Directory
    treats alice/ALICE/Alice as one principal sharing a single bad password
    count, so keying on the raw input would let an attacker cycle case to
    stay under our limit while still burning the directory's."""
    return username.strip().lower()


def ip_key(client_ip: str) -> str:
    return f"ip:{client_ip}"


def pair_key(username: str, client_ip: str | None) -> str:
    return f"{username}|{client_ip or _UNKNOWN_ADDRESS}"


def pair_prefix(username: str) -> str:
    """The start every pair key of `username` shares, for releasing them
    all at once."""
    return f"{username}|"


def delay_key(username: str) -> str:
    return f"delay:{username}"


class LoginThrottle:
    def __init__(self, attempts: ILoginAttemptTracker) -> None:
        self._attempts = attempts

    async def assert_allowed(self, username: str, client_ip: str | None) -> None:
        """Raises LoginLockedError while any scope of this attempt is locked,
        with the longest remaining wait. Runs before the credential is
        judged, so a refused attempt costs nothing and reveals nothing."""
        name = normalise_username(username)
        keys = [pair_key(name, client_ip), delay_key(name)]
        if client_ip:
            keys.append(ip_key(client_ip))
        wait = 0
        for key in keys:
            wait = max(wait, await self._attempts.lock_ttl(key))
        if wait > 0:
            raise LoginLockedError(LOCKED_MESSAGE, retry_after_seconds=wait)

    async def record_failure(
        self, username: str, client_ip: str | None, security: AdminSecuritySettings
    ) -> list[str]:
        """Counts one wrong password on every scope and locks or delays the
        scopes that reached their limit. Returns the scopes this failure
        locked, and the username scope only when its delay begins, not on
        every further failure that lengthens it."""
        name = normalise_username(username)
        locked: list[str] = []
        if client_ip and await self._record_address_failure(client_ip):
            locked.append(SCOPE_ADDRESS)

        pair = pair_key(name, client_ip)
        if lockout_triggered(
            await self._attempts.record_failure(pair), security.max_login_attempts
        ):
            await self._attempts.lock(pair, lockout_seconds(security.lockout_duration_minutes))
            locked.append(SCOPE_ACCOUNT_ON_ADDRESS)

        failures = await self._attempts.record_failure(name)
        delay = username_delay_seconds(failures, security.max_login_attempts)
        if delay > 0:
            await self._attempts.lock(delay_key(name), delay)
            if failures == security.max_login_attempts:
                locked.append(SCOPE_ACCOUNT)
        return locked

    async def record_success(self, username: str, client_ip: str | None) -> None:
        """Forgets the username's failures after its password was proven."""
        name = normalise_username(username)
        await self._attempts.reset(name)
        await self._attempts.reset(delay_key(name))
        await self._attempts.reset(pair_key(name, client_ip))

    async def release(self, username: str) -> None:
        """Releases every lock and counter of `username`, on every address,
        for the `admin unlock-users --user` recovery command."""
        name = normalise_username(username)
        await self._attempts.reset(name)
        await self._attempts.reset(delay_key(name))
        await self._attempts.release_prefix(pair_prefix(name))

    async def _record_address_failure(self, client_ip: str) -> bool:
        """Counts in fixed windows, so the count of an address many people
        share starts over instead of adding up for a whole day. Returns
        whether this failure locked the address."""
        window_key = f"{ip_key(client_ip)}@{ip_failure_window(now_utc().timestamp())}"
        if ip_lockout_triggered(await self._attempts.record_failure(window_key)):
            await self._attempts.reset(window_key)
            await self._attempts.lock(ip_key(client_ip), IP_LOCK_SECONDS)
            return True
        return False
