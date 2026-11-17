"""
Short-lived counters behind the login throttle and other attempt-limited
actions such as the per-user mail rate limit. `key` is an opaque scope chosen
by the caller (a username, `ip:{address}`, `mail:{user_id}`), so one store
holds counters for several features without collisions. The store holds no
policy; limits and durations come from the caller. Losing its state only
forgets attempts and never locks anyone out wrongly, so while Redis is
unavailable the Redis adapter falls back to an in-process store rather than
failing closed.
"""

from typing import Protocol


class ILoginAttemptTracker(Protocol):
    async def record_failure(self, key: str) -> int:
        """Counts one failed attempt or rate-limited send and returns the new
        total."""
        ...

    async def reset(self, key: str) -> None:
        """Forgets this scope's failures after a successful login."""
        ...

    async def lock(self, key: str, seconds: int) -> None:
        """Refuses this scope for `seconds`."""
        ...

    async def lock_ttl(self, key: str) -> int:
        """Seconds until the lock expires; 0 when not locked."""
        ...

    async def claim(self, key: str, seconds: int) -> bool:
        """Locks this scope for `seconds` unless it is locked already, as one
        atomic step. Returns whether this call took the lock, so a caller can
        allow at most one action per period (e.g. one time tracking journal
        fetch per user every few seconds) without counting failures."""
        ...

    async def release_prefix(self, prefix: str) -> int:
        """Releases every lock and counter whose key starts with `prefix`
        and returns how many keys were removed, so one username's locks on
        every address can be released at once."""
        ...

    async def clear_all(self) -> int:
        """Releases every lock and counter and returns how many keys were
        removed, for the `admin unlock-users` recovery command."""
        ...
