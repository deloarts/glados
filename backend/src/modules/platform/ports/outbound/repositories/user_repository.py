"""
Abstract interface for user persistence. The application layer depends
on this, never on the concrete SQLAlchemy implementation.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.user import User


@dataclass
class UserFilterDto:
    skip: int | None = None
    limit: int | None = None
    id: int | None = None
    username: str | None = None
    full_name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    is_service_account: bool | None = None
    search: str | None = None
    # False keeps `search` to username and full name, for the user directory
    # every signed-in user reads, so the search cannot probe e-mail addresses.
    search_includes_email: bool = True
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IUserRepository(Protocol):
    async def get_by_id(self, id: int) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_username_ci(self, username: str) -> User | None:
        """Case-insensitive username lookup, username only (unlike
        get_by_username_or_email, which also matches the e-mail column),
        used by PDM user matching (application.services.pdm_users.
        resolve_pdm_user, ListPdmUsers) to guess a link from a vault
        user's login name."""
        ...

    async def get_by_email_ci(self, email: str) -> User | None:
        """Case-insensitive e-mail lookup, used by ListPdmUsers as the
        fallback match for a vault user whose username did not resolve to
        a Glados user."""
        ...

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        """
        Resolve a login identifier that may be either a username or an e-mail
        address. Matching is case-insensitive and ignores surrounding
        whitespace. Returns inactive users too, the active check belongs to
        the use case, as with get_by_username/get_by_email.
        """
        ...

    async def get_by_rfid(self, rfid: str) -> User | None:
        """
        Resolves an RFID tag to its active owning user, or None, through the
        HMAC lookup index in O(1) (see SqlAlchemyUserRepository.get_by_rfid).
        Only reads.
        """
        ...

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]: ...

    async def save(self, user: User) -> User:
        """
        Insert or update without committing. The implementation decides
        whether to INSERT or UPDATE based on whether user.id already exists.
        """
        ...

    async def delete(self, user: User) -> None:
        """Deletes the row without committing."""
        ...
