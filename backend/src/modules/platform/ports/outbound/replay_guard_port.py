"""
One-shot claiming of a short-lived key, which stops an otherwise valid
credential from being replayed within its validity window, such as a TOTP
code intercepted after its holder submitted it (totp.verify_totp_once). It is
kept apart from ILoginAttemptTracker, which counts failures, because this
only asks whether an already valid value was seen before.
"""

from typing import Protocol


class IReplayGuard(Protocol):
    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        """Atomically claims `key` for `ttl_seconds`. True the first time a
        given key is claimed; False on every later call while the claim is
        still live."""
        ...
