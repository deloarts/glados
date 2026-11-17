"""
Rules for user groups. Managing groups needs write:settings, the permission
that already guards every permission change on users. Nobody can raise
their own permissions through a group: an actor cannot change their own
memberships, nor the permissions of a group they belong to. The system
user belongs to no group and so is never held back by that.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_group import UserGroup
from src.modules.platform.domain.exceptions import InvalidUserGroupError
from src.modules.platform.domain.exceptions import OwnUserGroupError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission

MAX_GROUP_NAME_LENGTH = 100
MAX_GROUP_DESCRIPTION_LENGTH = 500


class UserGroupRules:
    @staticmethod
    def assert_can_write(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_SETTINGS, "change", "user groups")

    @staticmethod
    def normalize_name(name: str) -> str:
        """The trimmed name, refused when empty or too long."""
        trimmed = name.strip()
        if not trimmed:
            raise InvalidUserGroupError("A group needs a name.")
        if len(trimmed) > MAX_GROUP_NAME_LENGTH:
            raise InvalidUserGroupError(
                f"A group name has at most {MAX_GROUP_NAME_LENGTH} characters."
            )
        return trimmed

    @staticmethod
    def assert_permissions_assignable(permissions: list[str]) -> None:
        """A group holds known permissions only, and never the terminal
        connect permission, which belongs to the account of a terminal key
        alone."""
        unknown = set(permissions) - set(Permission.ALL)
        if unknown:
            raise InvalidUserGroupError(f"Unknown permission(s): {sorted(unknown)}.")
        if Permission.CONNECT_TERMINALS in permissions:
            raise InvalidUserGroupError(
                f"{Permission.CONNECT_TERMINALS} is held only by terminal keys."
            )

    @staticmethod
    def assert_valid_member(candidate: User | None, member_id: int) -> None:
        """Personal and shared accounts can be members. Service accounts take
        their permissions from their API key, and the system user passes every
        check anyway, so neither belongs in a group."""
        if candidate is None:
            raise InvalidUserGroupError(f"User #{member_id} does not exist.")
        if candidate.is_systemuser:
            raise InvalidUserGroupError("The system user cannot be a group member.")
        if candidate.is_service_account:
            raise InvalidUserGroupError(
                f"User #{candidate.id} ({candidate.username!r}) is a service account "
                "and cannot be a group member."
            )

    @staticmethod
    def assert_not_own_membership(actor: User, before: list[int], after: list[int]) -> None:
        """Refuses a member list that adds or removes the actor."""
        if (actor.id in before) != (actor.id in after):
            raise OwnUserGroupError("You cannot change your own group memberships.")

    @staticmethod
    def assert_not_own_group_permissions(
        actor: User, group: UserGroup, permissions: list[str]
    ) -> None:
        """Refuses a permission change on a group the actor belongs to."""
        if actor.id in group.member_ids and set(permissions) != set(group.permissions):
            raise OwnUserGroupError("You cannot change the permissions of a group you belong to.")


def effective_permission_changes(
    before: dict[int, set[str]], after: dict[int, set[str]]
) -> list[int]:
    """The ids, sorted, of the users whose effective permissions differ
    between the two snapshots. A user missing from one side counts as
    holding nothing there."""
    ids = before.keys() | after.keys()
    return sorted(i for i in ids if before.get(i, set()) != after.get(i, set()))
