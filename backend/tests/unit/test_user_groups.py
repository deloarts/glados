"""
User groups at the domain level: a user's effective permissions are their
direct grants plus their groups' permissions, the group rules refuse
unknown and terminal permissions, ineligible members and every way of
raising one's own permissions, and a personal access token never carries a
permission its owner no longer holds.
"""

from dataclasses import replace

import pytest

from src.modules.platform.application.use_cases.pat.validate_pat import ValidatePat
from src.modules.platform.domain.entities.user_group import UserGroup
from src.modules.platform.domain.exceptions import InvalidUserGroupError
from src.modules.platform.domain.exceptions import OwnUserGroupError
from src.modules.platform.domain.services.token_permission_rules import (
    assert_requested_permissions_allowed,
)
from src.modules.platform.domain.services.user_group_rules import UserGroupRules
from src.modules.platform.domain.services.user_group_rules import effective_permission_changes
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.pat import hash_pat
from tests.factories import make_user
from tests.unit.test_pat_use_cases import FakePatRepository
from tests.unit.test_pat_use_cases import FakeUserRepository
from tests.unit.test_pat_use_cases import make_token


def _group(**overrides: object) -> UserGroup:
    fields: dict[str, object] = {
        "id": 1,
        "created": None,
        "changed": None,
        "changes": [],
        "name": "Purchasing",
        "description": "",
        "permissions": [Permission.WRITE_ORDERS],
        "creator_id": 1,
        "member_ids": [],
    }
    fields.update(overrides)
    return UserGroup(**fields)  # type: ignore[arg-type]


class TestEffectivePermissions:
    def test_union_of_direct_and_group_permissions(self) -> None:
        user = make_user(
            permissions=[Permission.WRITE_ORDERS],
            group_permissions=[Permission.WRITE_ORDERS, Permission.WRITE_SUPPLIERS],
        )

        assert user.effective_permissions == sorted(
            [Permission.WRITE_ORDERS, Permission.WRITE_SUPPLIERS]
        )
        assert user.has_permission(Permission.WRITE_SUPPLIERS) is True
        assert user.has_permission(Permission.WRITE_SETTINGS) is False

    def test_a_token_can_be_granted_a_permission_held_only_through_a_group(self) -> None:
        user = make_user(permissions=[], group_permissions=[Permission.WRITE_BOUGHT_ITEMS])

        assert_requested_permissions_allowed(
            [Permission.WRITE_BOUGHT_ITEMS],
            user,
            exception_class=InvalidUserGroupError,
            noun="A token",
        )


class TestGroupRules:
    def test_unknown_and_terminal_permissions_are_refused(self) -> None:
        with pytest.raises(InvalidUserGroupError):
            UserGroupRules.assert_permissions_assignable(["write:nothing"])
        with pytest.raises(InvalidUserGroupError):
            UserGroupRules.assert_permissions_assignable([Permission.CONNECT_TERMINALS])

    def test_system_and_service_accounts_cannot_be_members(self) -> None:
        UserGroupRules.assert_valid_member(make_user(id=2, is_shared_account=True), 2)
        with pytest.raises(InvalidUserGroupError):
            UserGroupRules.assert_valid_member(None, 9)
        with pytest.raises(InvalidUserGroupError):
            UserGroupRules.assert_valid_member(make_user(id=2, is_systemuser=True), 2)
        with pytest.raises(InvalidUserGroupError):
            UserGroupRules.assert_valid_member(make_user(id=2, is_service_account=True), 2)

    def test_an_empty_name_is_refused_and_a_name_is_trimmed(self) -> None:
        assert UserGroupRules.normalize_name("  QA  ") == "QA"
        with pytest.raises(InvalidUserGroupError):
            UserGroupRules.normalize_name("   ")

    def test_nobody_adds_or_removes_themselves(self) -> None:
        actor = make_user(id=5)
        UserGroupRules.assert_not_own_membership(actor, [5, 6], [5])
        with pytest.raises(OwnUserGroupError):
            UserGroupRules.assert_not_own_membership(actor, [], [5])
        with pytest.raises(OwnUserGroupError):
            UserGroupRules.assert_not_own_membership(actor, [5], [])

    def test_a_member_cannot_change_the_permissions_of_their_group(self) -> None:
        actor = make_user(id=5)
        group = _group(member_ids=[5])
        UserGroupRules.assert_not_own_group_permissions(actor, group, [Permission.WRITE_ORDERS])
        with pytest.raises(OwnUserGroupError):
            UserGroupRules.assert_not_own_group_permissions(
                actor, group, [Permission.WRITE_ORDERS, Permission.WRITE_SETTINGS]
            )
        UserGroupRules.assert_not_own_group_permissions(
            make_user(id=6), group, [Permission.WRITE_SETTINGS]
        )

    def test_only_users_whose_effective_permissions_changed_are_reported(self) -> None:
        before = {1: {"a"}, 2: {"a", "b"}, 3: {"c"}}
        after = {1: {"a"}, 2: {"a"}, 4: {"d"}}

        assert effective_permission_changes(before, after) == [2, 3, 4]


class TestPatCappedAtCurrentPermissions:
    async def test_a_token_loses_what_its_owner_lost_since(self) -> None:
        raw = "glados_pat_group-token"
        owner = make_user(id=1, permissions=[], group_permissions=[Permission.WRITE_BOUGHT_ITEMS])
        token = make_token(id=1, user_id=1, permissions=[Permission.WRITE_BOUGHT_ITEMS])
        token.token_hash = hash_pat(raw)
        users = FakeUserRepository([owner])
        use_case = ValidatePat(FakePatRepository([token]), users, hash_fn=hash_pat)

        user, _ = await use_case.execute(raw)
        assert user.has_permission(Permission.WRITE_BOUGHT_ITEMS) is True

        users._users[1] = replace(owner, group_permissions=[])
        user, _ = await use_case.execute(raw)
        assert user.has_permission(Permission.WRITE_BOUGHT_ITEMS) is False
        assert user.effective_permissions == []
