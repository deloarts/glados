"""
An API key authenticates as its own dedicated service-account User (see
User.is_service_account) rather than impersonating the human who created it.
`permissions` is fixed at creation time, a key cannot be changed, only
revoked, and is granted onto the backing User at the same time, so
User.has_permission() enforces it during normal request handling without any
special-casing elsewhere in the application layer.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.entities.base import Entity
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class ApiKey(Entity):
    name: str
    token_hash: str  # SHA-256 hex digest, the raw key value is never stored
    token_prefix: str  # leading chars of the raw key value, for display/identification only
    user_id: int  # the backing service-account User this key authenticates as
    permissions: list[str]
    created_by_id: int  # which human created this key, audit only, not authorization
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

    @property
    def is_terminal_key(self) -> bool:
        """Whether this is a terminal key, which only lets an unknown device
        register itself as a pending terminal."""
        return Permission.CONNECT_TERMINALS in self.permissions
