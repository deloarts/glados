"""
Abstract interface for UserTimeTrackingCredentials persistence, at most one
row per Glados user. The user name is plaintext on this side of the port and
encrypted at rest by the implementation; the password exists only sealed.
Writes flush and never commit, the calling use case's unit of work does.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)


@runtime_checkable
class IUserTimeTrackingCredentialsRepository(Protocol):
    async def get_by_user(self, user_id: int) -> UserTimeTrackingCredentials | None:
        """The user's row; the user name is None when it can no longer be
        decrypted."""
        ...

    async def list_all(self) -> list[UserTimeTrackingCredentials]:
        """Every stored row, for the admin's list of holders."""
        ...

    async def exists_for_user(self, user_id: int) -> bool: ...

    async def is_fingerprint_taken_by_other_user(self, fingerprint: str, user_id: int) -> bool:
        """Whether another user's row carries this user name fingerprint."""
        ...

    async def save(self, credentials: UserTimeTrackingCredentials) -> UserTimeTrackingCredentials:
        """Inserts the user's row or replaces every stored value of it.
        Raises TimeTrackingUserAlreadyLinkedError when the fingerprint is
        taken by another user's row in the meantime."""
        ...

    async def mark_auth_failed(self, user_id: int, at: datetime) -> None:
        """Sets only time_tracking_auth_failed_at, leaving the stored values
        untouched."""
        ...

    async def clear_sealed(self, user_id: int) -> None:
        """Drops the sealed value after the service reported a changed
        binding, so no further call is made with it."""
        ...

    async def delete_for_user(self, user_id: int) -> bool:
        """Removes the user's row; whether there was one."""
        ...

    async def delete_all(self) -> int:
        """Removes every row; how many there were."""
        ...

    async def get_count(self) -> int: ...
