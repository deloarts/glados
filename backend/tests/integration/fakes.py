"""
In-memory stand-ins for outbound ports, so the integration suite keeps
needing nothing but a throwaway SQLite file.
"""

from __future__ import annotations


class FakeLoginAttemptTracker:
    """In-memory ILoginAttemptTracker. `key` is an opaque scope string,
    a bare username for a login attempt, `mail:{user_id}` for the mail
    rate limit, `totp:{user_id}` for the TOTP-step throttle, see the
    port's docstring.

    `lock_ttl` returns whatever was set rather than counting down, the
    tests care that a lock exists and roughly how long it has left, not
    about real time passing. `expire()` makes a lock lapse on demand.
    """

    def __init__(self) -> None:
        self.failures: dict[str, int] = {}
        self.locks: dict[str, int] = {}

    async def record_failure(self, key: str) -> int:
        self.failures[key] = self.failures.get(key, 0) + 1
        return self.failures[key]

    async def reset(self, key: str) -> None:
        self.failures.pop(key, None)
        self.locks.pop(key, None)

    async def lock(self, key: str, seconds: int) -> None:
        self.locks[key] = seconds
        self.failures.pop(key, None)

    async def lock_ttl(self, key: str) -> int:
        return self.locks.get(key, 0)

    async def claim(self, key: str, seconds: int) -> bool:
        if self.locks.get(key, 0) > 0:
            return False
        self.locks[key] = seconds
        return True

    async def release_prefix(self, prefix: str) -> int:
        keys = [k for k in [*self.failures, *self.locks] if k.startswith(prefix)]
        for key in keys:
            self.failures.pop(key, None)
            self.locks.pop(key, None)
        return len(keys)

    async def clear_all(self) -> int:
        removed = len(self.failures) + len(self.locks)
        self.failures.clear()
        self.locks.clear()
        return removed

    # ── test helpers ──────────────────────────────────────────────────

    def expire(self, key: str) -> None:
        """Simulate the lock's TTL lapsing."""
        self.locks.pop(key, None)

    async def is_locked(self, key: str) -> bool:
        return await self.lock_ttl(key) > 0


class FakeReplayGuard:
    """In-memory IReplayGuard. `ttl_seconds` is accepted but not enforced,
    tests care whether a key has already been claimed, not about real time
    passing; `expire()` releases a claim on demand, same shape as
    FakeLoginAttemptTracker.expire above."""

    def __init__(self) -> None:
        self.claimed: set[str] = set()

    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True

    # ── test helpers ──────────────────────────────────────────────────

    def expire(self, key: str) -> None:
        self.claimed.discard(key)


class FakeBackupJobs:
    """In-memory IBackupJobs. Returns plausible storage keys and records how
    often each job ran, so a test can assert a run happened without a real
    pg_dump subprocess or a real storage snapshot ever being attempted."""

    def __init__(self) -> None:
        self.db_runs = 0
        self.file_runs = 0

    async def run_db(self) -> str:
        self.db_runs += 1
        return "backups/db/fake.sql.gz"

    async def run_files(self) -> str:
        self.file_runs += 1
        return "backups/files/fake/"
