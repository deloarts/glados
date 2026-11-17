"""
Repository interface for UserPdmLink, the mapping of several PDM users to one
Glados user (see the user mapping section of docs/PDM_INTEGRATION.md).
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.user_pdm_link import UserPdmLink


@runtime_checkable
class IUserPdmLinkRepository(Protocol):
    async def list_all(self) -> list[UserPdmLink]:
        """Every link, for ListPdmUsers to cross-reference the whole vault
        user list in one query rather than one per row."""
        ...

    async def list_by_user(self, user_id: int) -> list[UserPdmLink]:
        """Every PDM user linked to one Glados user, oldest link first, for
        UserResponse.pdm_links."""
        ...

    async def get_by_pdm_user_id(self, pdm_user_id: int) -> UserPdmLink | None:
        """The link of `pdm_user_id`, which is unique."""
        ...

    async def upsert(self, *, pdm_user_id: int, user_id: int, pdm_username: str) -> UserPdmLink:
        """Inserts a link, or moves an existing link of `pdm_user_id` onto
        `user_id` (see LinkPdmUsers). Either way pdm_username is refreshed to
        the vault's current name and linked_at is stamped anew."""
        ...

    async def delete_by_pdm_user_id(self, pdm_user_id: int) -> None:
        """Removes the link naming `pdm_user_id`, if any. A no-op when
        nothing is linked."""
        ...
