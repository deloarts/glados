"""
A personal access token (PAT) authenticates as the human user who created
it (see is_self on User) rather than as a separate identity, unlike an
ApiKey, which mints its own dedicated service-account User. A user may hold
several PATs at once, each with its own name and its own `permissions`
subset, fixed at creation time and capped at the creator's own permissions
(see PatRules). On every use the subset is capped again at what the owner
holds at that moment, so a permission the owner has lost since stops
working through the token too. The result is applied to the authenticated
request by replacing User.permissions for that request only, the stored
User record itself is untouched.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class PersonalAccessToken(Entity):
    name: str
    token_hash: str  # SHA-256 hex digest, the raw token value is never stored
    token_prefix: str  # leading chars of the raw token value, for display/identification only
    user_id: int  # the human user this token authenticates as
    permissions: list[str]
    created: datetime  # UTC, timezone-aware, see docs/DEVELOPMENT.md's datetime convention
    expires_at: datetime | None  # UTC, aware; None = never expires (flagged as a warning in web)
    revoked_at: datetime | None = None  # UTC, aware

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return now_utc() >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
