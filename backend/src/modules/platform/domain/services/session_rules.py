"""When a session is over.

Sessions are server-side rows; the JWT only names the row and carries no
expiry. A session ends by revocation, by the admin-configured idle timeout,
which restarts whenever the user does something, or by the absolute
lifetime, which counts from sign-in and does not move with activity. The
settings refuse an idle timeout of 0, and without an idle timeout the absolute
lifetime still bounds the session.

The web app reports with every request how long ago its user last
interacted with the page, so a request the app sends on its own, such as a
poll, does not count as activity. A request without that report counts as
activity at the time it arrives.

The system user's session hard-expires a fixed, much shorter time after
creation instead. That is deliberately not a setting, so the account
holding every permission cannot have its lifetime configured away.
"""

from datetime import datetime
from datetime import timedelta
from typing import Final

# How stale a session row's last_seen_at may be before it is worth
# writing a fresh value. Throttles the per-request UPDATE, not expiry.
LAST_SEEN_WRITE_INTERVAL_SECONDS = 60

SYSTEM_USER_SESSION_LIFETIME_MINUTES: Final = 15

# The shipped absolute lifetime of every other session, and the one used
# when the security settings row cannot be read.
DEFAULT_SESSION_MAX_LIFETIME_DAYS: Final = 30


def session_expired(last_seen_at: datetime, timeout_minutes: int, now: datetime) -> bool:
    """Idle-expiry rule. Non-positive timeouts never expire."""
    if timeout_minutes <= 0:
        return False
    return now > last_seen_at + timedelta(minutes=timeout_minutes)


def last_activity(now: datetime, idle_seconds: int | None) -> datetime:
    """When the user last did something, as a request reports it; `now`
    for a request that reports nothing. A negative report counts as none."""
    if idle_seconds is None or idle_seconds <= 0:
        return now
    return now - timedelta(seconds=idle_seconds)


def last_seen_touch_due(last_seen_at: datetime, now: datetime) -> bool:
    """Whether last_seen_at is stale enough to rewrite (see constant above)."""
    return now - last_seen_at > timedelta(seconds=LAST_SEEN_WRITE_INTERVAL_SECONDS)


def session_hard_expiry(
    created_at: datetime, *, is_systemuser: bool, max_lifetime_days: int
) -> datetime:
    """When the absolute lifetime ends: the fixed system user lifetime, or
    `max_lifetime_days` after sign-in for everyone else. A non-positive
    setting falls back to the shipped default rather than to no limit."""
    if is_systemuser:
        return created_at + timedelta(minutes=SYSTEM_USER_SESSION_LIFETIME_MINUTES)
    days = max_lifetime_days if max_lifetime_days > 0 else DEFAULT_SESSION_MAX_LIFETIME_DAYS
    return created_at + timedelta(days=days)


def session_hard_expired(
    created_at: datetime, is_systemuser: bool, now: datetime, max_lifetime_days: int
) -> bool:
    """Whether the absolute lifetime has passed."""
    expiry = session_hard_expiry(
        created_at, is_systemuser=is_systemuser, max_lifetime_days=max_lifetime_days
    )
    return now > expiry
