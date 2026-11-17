"""
Abstract interface for passkey persistence. Writes flush without
committing; the calling use case commits.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.platform.domain.entities.passkey import Passkey


@runtime_checkable
class IPasskeyRepository(Protocol):
    async def get_by_credential_id(self, credential_id: bytes) -> Passkey | None: ...

    async def get_for_user(self, user_id: int, public_id: UUID) -> Passkey | None:
        """The user's own passkey, or None when none of theirs matches."""
        ...

    async def list_for_user(self, user_id: int) -> list[Passkey]:
        """The user's passkeys, newest first."""
        ...

    async def save(self, passkey: Passkey) -> Passkey:
        """Insert (id == 0) or update (id > 0). The legitimate updates are a
        new name and stamping sign_count and last_used_at after a login."""
        ...

    async def delete_by_public_id(self, user_id: int, public_id: UUID) -> bool:
        """Deletes the user's own passkey. Returns False when none of theirs
        matches."""
        ...

    async def delete_all_for_user(self, user_id: int) -> int:
        """Deletes every passkey of the user. Returns the count."""
        ...
