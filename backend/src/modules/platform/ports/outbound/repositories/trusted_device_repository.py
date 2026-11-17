"""
Abstract interface for trusted-device persistence (TOTP "don't ask again").
Writes flush without committing; the calling use case commits.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.platform.domain.entities.trusted_device import TrustedDevice


@runtime_checkable
class ITrustedDeviceRepository(Protocol):
    async def get_by_token_hash(self, token_hash: str) -> TrustedDevice | None: ...

    async def list_for_user(self, user_id: int) -> list[TrustedDevice]:
        """Unrevoked, unexpired trust grants, newest first."""
        ...

    async def save(self, device: TrustedDevice) -> TrustedDevice:
        """Insert (id == 0) or update (id > 0). Grants are otherwise
        immutable, legitimate updates are stamping last_used_at and
        revoked_at."""
        ...

    async def revoke_by_public_id(self, user_id: int, public_id: UUID) -> bool:
        """Stamps revoked_at on the user's own grant. Returns False when no
        live grant of theirs matches."""
        ...

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Stamps revoked_at on every live grant. Returns the count. Called
        whenever a vouched-for factor changes: password change, TOTP
        disable/reset, force-logout."""
        ...
