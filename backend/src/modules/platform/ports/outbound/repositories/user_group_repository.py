"""
Repository interface for user groups, the named permission bundles every
member inherits. A tenant holds a handful of them, so readers take the
whole list.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.user_group import UserGroup


@runtime_checkable
class IUserGroupRepository(Protocol):
    async def list_all(self) -> list[UserGroup]:
        """Every group with its member ids, by name."""
        ...

    async def get_by_id(self, id: int) -> UserGroup | None: ...

    async def get_by_name_ci(self, name: str) -> UserGroup | None:
        """The group with this name, compared regardless of case."""
        ...

    async def save(self, group: UserGroup) -> UserGroup:
        """Insert (id == 0) or update (id > 0), members included. Flushes
        without committing."""
        ...

    async def delete(self, group: UserGroup) -> None:
        """Removes the group and its memberships. Flushes without committing."""
        ...
