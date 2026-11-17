"""
A device the user chose to trust at the TOTP step ("don't ask again on
this device"), GitHub-style. The browser holds a random secret in an
httpOnly cookie; only its SHA-256 hash is stored here, so a database
leak yields nothing replayable, same posture as PATs.

Trust skips the *second* factor only: the password is still required on
every login. Unlike sessions, trust is always bounded (`expires_at` is
non-null, from AdminSecuritySettings.totp_trusted_device_days) and is
revoked wholesale whenever the factors it vouches for change, password
change, TOTP disable or admin reset, force-logout.
"""

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class TrustedDevice(Entity):
    user_id: int
    token_hash: str  # SHA-256 hex digest, the raw cookie value is never stored
    created_at: datetime  # UTC, timezone-aware
    last_used_at: datetime  # UTC, aware; when the cookie last skipped a TOTP prompt
    expires_at: datetime  # UTC, aware; always bounded, unlike sessions
    user_agent: str | None
    revoked_at: datetime | None = None  # UTC, aware

    @property
    def is_expired(self) -> bool:
        return now_utc() >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_usable(self) -> bool:
        return not self.is_revoked and not self.is_expired


def make_trusted_device(
    user_id: int, token_hash: str, trust_days: int, user_agent: str | None
) -> TrustedDevice:
    """A fresh, unpersisted trust grant (id=0) valid for trust_days."""
    now = now_utc()
    return TrustedDevice(
        id=0,
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=trust_days),
        user_agent=user_agent,
    )
