"""
Simple read use cases.

The full user view, GetUser and GetUsers, belongs to user administration;
every other signed-in user reads the reduced view through GetUserDirectory
(see UserRules.assert_can_read_details).
"""

from dataclasses import replace

from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.dto.user_dto import UserSummaryResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto


class PaginatedUsers:
    def __init__(self, total: int, items: list[UserResult]):
        self.total = total
        self.items = items


class PaginatedUserSummaries:
    def __init__(self, total: int, items: list[UserSummaryResult]):
        self.total = total
        self.items = items


class GetUser:
    def __init__(self, user_repo: IUserRepository, link_repo: IUserPdmLinkRepository) -> None:
        self._repo = user_repo
        self._links = link_repo

    async def execute(self, actor: User, user_id: int) -> UserResult:
        UserRules.assert_can_read_details(actor, user_id)
        user = found_or_raise(
            await self._repo.get_by_id(user_id), UserNotFoundError, f"User #{user_id} not found."
        )
        return UserMapper.to_result(user, await self._links.list_by_user(user.id))


class GetUsers:
    def __init__(self, user_repo: IUserRepository, link_repo: IUserPdmLinkRepository) -> None:
        self._repo = user_repo
        self._links = link_repo

    async def execute(self, actor: User, filters: UserFilterDto) -> PaginatedUsers:
        UserRules.assert_can_read_details(actor)
        total, users = await self._repo.get_multi(filters)
        return PaginatedUsers(
            total=total,
            items=[UserMapper.to_result(u, await self._links.list_by_user(u.id)) for u in users],
        )


# The columns the directory may sort by: what it shows, nothing it hides.
DIRECTORY_ORDER_COLUMNS = frozenset({"id", "username", "full_name"})


class GetUserDirectory:
    """The reduced user list every signed-in user may read. Its filters and
    its sort never reach the e-mail column, so they cannot probe addresses."""

    def __init__(self, user_repo: IUserRepository) -> None:
        self._repo = user_repo

    async def execute(self, filters: UserFilterDto) -> PaginatedUserSummaries:
        order_by = filters.order_by if filters.order_by in DIRECTORY_ORDER_COLUMNS else None
        total, users = await self._repo.get_multi(
            replace(filters, email=None, search_includes_email=False, order_by=order_by)
        )
        return PaginatedUserSummaries(
            total=total, items=[UserMapper.to_summary_result(u) for u in users]
        )
