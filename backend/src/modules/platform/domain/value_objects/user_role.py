"""
Immutable snapshot of a user's effective permissions at a point in time.
System users bypass all permission checks; everyone else is checked against
their explicit permissions list.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.platform.domain.entities.user import User


@dataclass(frozen=True)
class UserRole:
    is_systemuser: bool
    permissions: tuple[str, ...]

    @classmethod
    def from_user(cls, user: "User") -> "UserRole":
        return cls(
            is_systemuser=user.is_systemuser,
            permissions=tuple(user.permissions),
        )

    def has(self, permission: str) -> bool:
        if self.is_systemuser:
            return True
        return permission in self.permissions
