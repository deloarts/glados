"""Operator-selection use case for shared-account sessions. Returns eligible
operators (active, non-service, non-shared-account users). Shared-account
actors see only their assigned members; personal accounts see all eligible
operators.
"""

from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto


class GetOperators:
    def __init__(self, user_repo: IUserRepository) -> None:
        self._users = user_repo

    async def execute(self, actor: User) -> list[PublicUserResult]:
        users = await fetch_all(
            lambda skip, limit: self._users.get_multi(
                UserFilterDto(is_active=True, skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        eligible = [u for u in users if not u.is_service_account and not u.is_shared_account]
        if actor.is_shared_account:
            eligible = [u for u in eligible if u.id in actor.member_ids]
        return [UserMapper.to_public_result(u) for u in eligible]
