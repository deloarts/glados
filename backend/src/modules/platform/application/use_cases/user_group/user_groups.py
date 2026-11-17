"""
User groups: list, create, update and delete. Every signed-in user can read
the groups, as they can read the users; changes need write:settings. A
change that alters what a user may do tells that user, through the same
UserPermissionsChanged event a direct permission change publishes, and only
users whose effective permissions really changed hear about it.

Creating and deleting a group, and changing its permissions or members, are
recorded in the security log; a change of name or description alone is
not.
"""

from src.modules.platform.application.dto.user_group_dto import SaveUserGroupCommand
from src.modules.platform.application.dto.user_group_dto import UserGroupResult
from src.modules.platform.application.mappers.user_group_mapper import UserGroupMapper
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_group import UserGroup
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.domain.exceptions import UserGroupNameTakenError
from src.modules.platform.domain.exceptions import UserGroupNotFoundError
from src.modules.platform.domain.services.user_group_rules import UserGroupRules
from src.modules.platform.domain.services.user_group_rules import effective_permission_changes
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ListUserGroups:
    def __init__(self, group_repo: IUserGroupRepository) -> None:
        self._groups = group_repo

    async def execute(self) -> list[UserGroupResult]:
        return [UserGroupMapper.to_result(g) for g in await self._groups.list_all()]


class _GroupChange:
    """What the create, update and delete use cases share: the members they
    touch, loaded once, and the notifications for those whose effective
    permissions the change altered."""

    def __init__(
        self,
        group_repo: IUserGroupRepository,
        user_repo: IUserRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._groups = group_repo
        self._users = user_repo
        self._bus = event_bus
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def _load_users(self, ids: set[int]) -> dict[int, User | None]:
        return {i: await self._users.get_by_id(i) for i in sorted(ids)}

    async def _validated_members(
        self, users: dict[int, User | None], before: list[int], after: list[int]
    ) -> list[int]:
        """Checks only the members being added, so a member who no longer
        qualifies does not block an unrelated edit of the group."""
        for member_id in sorted(set(after) - set(before)):
            UserGroupRules.assert_valid_member(users.get(member_id), member_id)
        return sorted(set(after))

    async def _assert_name_free(self, name: str, group_id: int) -> None:
        existing = await self._groups.get_by_name_ci(name)
        if existing is not None and existing.id != group_id:
            raise UserGroupNameTakenError(f"A group named {name!r} already exists.")

    async def _notify(self, actor: User, before: dict[int, set[str]]) -> None:
        """Compares `before` with the effective permissions the users hold
        now that the change is flushed, and publishes one event per user
        whose permissions differ."""
        groups = await self._groups.list_all()
        users = await self._load_users(set(before))
        after = {
            uid: set(u.permissions)
            | {p for g in groups if uid in g.member_ids for p in g.permissions}
            for uid, u in users.items()
            if u is not None
        }
        for uid in effective_permission_changes(before, after):
            await self._bus.publish(UserPermissionsChanged(user_id=uid, actor_id=actor.id))


def _add_difference[T: (str, int)](
    detail: dict[str, object], key: str, before: list[T], after: list[T]
) -> None:
    """Adds what `after` added to and removed from `before` under
    `{key}_added` and `{key}_removed`, leaving out an empty side."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    if added:
        detail[f"{key}_added"] = added
    if removed:
        detail[f"{key}_removed"] = removed


def _effective(users: dict[int, User | None]) -> dict[int, set[str]]:
    return {uid: set(u.effective_permissions) for uid, u in users.items() if u is not None}


class CreateUserGroup(_GroupChange):
    async def execute(self, actor: User, cmd: SaveUserGroupCommand) -> UserGroupResult:
        UserGroupRules.assert_can_write(actor)
        name = UserGroupRules.normalize_name(cmd.name)
        UserGroupRules.assert_permissions_assignable(cmd.permissions)
        UserGroupRules.assert_not_own_membership(actor, [], cmd.member_ids)
        await self._assert_name_free(name, 0)
        users = await self._load_users(set(cmd.member_ids))
        member_ids = await self._validated_members(users, [], cmd.member_ids)
        before = _effective(users)

        now = now_utc()
        saved = await self._groups.save(
            UserGroup(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog([], actor.full_name, "Group created."),
                name=name,
                description=cmd.description.strip(),
                permissions=sorted(set(cmd.permissions)),
                creator_id=actor.id,
                member_ids=member_ids,
            )
        )
        await self._audit.record(
            SecurityEventType.GROUP_CREATED,
            actor=actor,
            target_id=saved.id,
            detail={
                "name": saved.name,
                "permissions": saved.permissions,
                "member_ids": saved.member_ids,
            },
        )
        await self._notify(actor, before)
        await self._uow.commit()
        log.info(f"Created user group #{saved.id} {saved.name!r}.")
        return UserGroupMapper.to_result(saved)


class UpdateUserGroup(_GroupChange):
    async def _record_change(
        self,
        actor: User,
        group: UserGroup,
        permissions_before: list[str],
        members_before: list[int],
    ) -> None:
        """Records the permissions and members the update added and
        removed, nothing when it changed neither."""
        detail: dict[str, object] = {"name": group.name}
        _add_difference(detail, "permissions", permissions_before, group.permissions)
        _add_difference(detail, "members", members_before, group.member_ids)
        if len(detail) == 1:
            return
        await self._audit.record(
            SecurityEventType.GROUP_CHANGED, actor=actor, target_id=group.id, detail=detail
        )

    async def execute(
        self, actor: User, group_id: int, cmd: SaveUserGroupCommand
    ) -> UserGroupResult:
        UserGroupRules.assert_can_write(actor)
        group = await self._groups.get_by_id(group_id)
        if group is None:
            raise UserGroupNotFoundError(f"Group #{group_id} not found.")
        name = UserGroupRules.normalize_name(cmd.name)
        UserGroupRules.assert_permissions_assignable(cmd.permissions)
        UserGroupRules.assert_not_own_group_permissions(actor, group, cmd.permissions)
        UserGroupRules.assert_not_own_membership(actor, group.member_ids, cmd.member_ids)
        await self._assert_name_free(name, group.id)
        users = await self._load_users(set(group.member_ids) | set(cmd.member_ids))
        member_ids = await self._validated_members(users, group.member_ids, cmd.member_ids)
        before = _effective(users)
        permissions_before = list(group.permissions)
        members_before = list(group.member_ids)

        group.name = name
        group.description = cmd.description.strip()
        group.permissions = sorted(set(cmd.permissions))
        group.member_ids = member_ids
        group.changed = now_utc()
        group.changes = append_changelog(group.changes, actor.full_name, "Group updated.")
        saved = await self._groups.save(group)
        await self._record_change(actor, saved, permissions_before, members_before)
        await self._notify(actor, before)
        await self._uow.commit()
        log.info(f"Updated user group #{group_id}.")
        return UserGroupMapper.to_result(saved)


class DeleteUserGroup(_GroupChange):
    """Never blocked by members: they simply lose what only this group gave
    them, and the confirm dialog names them beforehand."""

    async def execute(self, actor: User, group_id: int) -> None:
        UserGroupRules.assert_can_write(actor)
        group = await self._groups.get_by_id(group_id)
        if group is None:
            raise UserGroupNotFoundError(f"Group #{group_id} not found.")
        before = _effective(await self._load_users(set(group.member_ids)))
        await self._audit.record(
            SecurityEventType.GROUP_DELETED,
            actor=actor,
            target_id=group.id,
            detail={
                "name": group.name,
                "permissions": group.permissions,
                "member_ids": group.member_ids,
            },
        )
        await self._groups.delete(group)
        await self._notify(actor, before)
        await self._uow.commit()
        log.info(f"Deleted user group #{group_id} with {len(group.member_ids)} member(s).")
