"""
Abstract interface for server-side session persistence.
Writes flush without committing; the calling use case commits.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.platform.domain.entities.user_session import UserSession


@runtime_checkable
class IUserSessionRepository(Protocol):
    async def get_by_public_id(self, public_id: UUID) -> UserSession | None: ...

    async def list_for_user(self, user_id: int) -> list[UserSession]:
        """Unrevoked sessions, most recently seen first. Idle-expired rows
        are included, filtering those is the caller's job, since only it
        knows the configured timeout."""
        ...

    async def save(self, session: UserSession) -> UserSession:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def touch_last_seen(self, public_id: UUID, when: datetime) -> None:
        """Stamps last_seen_at without an entity round trip, this runs on
        (throttled) every authenticated request."""
        ...

    async def revoke_by_public_id(self, user_id: int, public_id: UUID) -> bool:
        """Stamps revoked_at on the user's own session. Returns False when
        no live session of theirs matches, user_id scoping is what stops
        one user revoking another's session by guessing ids."""
        ...

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Stamps revoked_at on every live session. Returns the count."""
        ...

    async def revoke_all_for_user_except(self, user_id: int, keep_public_id: UUID | None) -> int:
        """Same, but spares one session, "sign out everywhere else" and
        password change both keep the session that initiated them. A None
        keep_public_id revokes everything, same as revoke_all_for_user."""
        ...
