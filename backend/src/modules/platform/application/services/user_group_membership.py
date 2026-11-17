"""
Checks the groups a user is put into from the user side, by the create and
update user use cases. The group side checks its members itself, in the
user group use cases.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InvalidUserGroupError
from src.modules.platform.domain.services.user_group_rules import UserGroupRules
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)


async def validated_group_ids(
    groups: IUserGroupRepository | None, user: User, group_ids: list[int]
) -> list[int]:
    """The ids deduplicated and sorted, once every group exists and `user`
    may be a member at all. `user` is the account as it will be saved."""
    if not group_ids:
        return []
    if groups is None:
        raise InvalidUserGroupError("Groups cannot be assigned here.")
    UserGroupRules.assert_valid_member(user, user.id)
    known = {g.id for g in await groups.list_all()}
    unknown = sorted(set(group_ids) - known)
    if unknown:
        raise InvalidUserGroupError(f"Unknown group(s): {unknown}.")
    return sorted(set(group_ids))
