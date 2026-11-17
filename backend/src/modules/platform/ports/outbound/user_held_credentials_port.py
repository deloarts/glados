"""
Credentials a user holds for an outside system, such as the time tracking
system. Only a personal account may hold them, and they go with the account
when it is deactivated or deleted. The user code needs no more than this;
the module that owns the credentials implements it and the composition root
wires it in.
"""

from typing import Protocol


class IUserHeldCredentials(Protocol):
    async def exists_for_user(self, user_id: int) -> bool: ...

    async def delete_for_user(self, user_id: int) -> bool:
        """Deletes the user's credentials; True when there were any."""
        ...
