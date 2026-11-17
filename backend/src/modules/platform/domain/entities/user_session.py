"""
A signed-in browser session, GitHub-style: the server-side row is the
authority on whether the session is alive. The JWT handed to the client
only names this row (its `sid` claim is the row's public_id) and carries
no expiry of its own, expiry is the idle rule in
domain/services/session_rules.py applied to `last_seen_at`, and
revocation is stamping `revoked_at` (self-service sessions list, admin
force-logout, password change).

`user_agent`/`ip` exist purely so the sessions list can answer "which
device is this?", they are display metadata, never used for auth.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class UserSession(Entity):
    user_id: int
    created_at: datetime  # UTC, timezone-aware, see docs/DEVELOPMENT.md's datetime convention
    last_seen_at: datetime  # UTC, aware; drives idle expiry
    user_agent: str | None
    ip: str | None
    revoked_at: datetime | None = None  # UTC, aware

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


def make_user_session(user_id: int, user_agent: str | None, ip: str | None) -> UserSession:
    """A fresh, unpersisted session (id=0) starting now."""
    now = now_utc()
    return UserSession(
        id=0,
        user_id=user_id,
        created_at=now,
        last_seen_at=now,
        user_agent=user_agent,
        ip=ip,
    )
