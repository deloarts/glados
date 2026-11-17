"""
Direct unit tests for src/modules/platform/domain/services/designated_user_rules.py, the
shared "who may this product/project be assigned to" rules behind
ProductRules/ProjectRules.

The pair is deliberately asymmetric (create silently forces, update
rejects), so the tests are written to make that contrast explicit: the
same actor and the same requested user id produce different outcomes
depending on which function is called. A refactor that "unified" them
would break these, which is the point, update must not go back to
silently rewriting the request, and create must not start 403-ing.
"""

import pytest

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.designated_user_rules import (
    assert_can_assign_designated_user,
)
from src.modules.platform.domain.services.designated_user_rules import resolve_designated_user
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.domain.services.project_rules import ProjectRules
from tests.factories import make_user

ACTOR_ID = 7
OTHER_ID = 99


def manager() -> User:
    return make_user(id=ACTOR_ID, permissions=[Permission.MANAGE_PROJECTS])


def writer() -> User:
    return make_user(id=ACTOR_ID, permissions=[Permission.WRITE_PROJECTS])


# ── resolve_designated_user (create-time) ─────────────────────────────


class TestResolveDesignatedUser:
    def test_non_manager_is_always_assigned_themselves(self):
        assert resolve_designated_user(writer(), OTHER_ID) == ACTOR_ID

    def test_non_manager_omitting_the_field_gets_themselves(self):
        assert resolve_designated_user(writer(), None) == ACTOR_ID

    def test_manager_may_assign_another_user(self):
        assert resolve_designated_user(manager(), OTHER_ID) == OTHER_ID

    def test_manager_omitting_the_field_gets_themselves(self):
        assert resolve_designated_user(manager(), None) == ACTOR_ID

    def test_zero_is_treated_as_unset(self):
        """`designated_user_id or actor.id`, 0 is falsy, so it means
        "unset", not "user #0"."""
        assert resolve_designated_user(manager(), 0) == ACTOR_ID


# ── assert_can_assign_designated_user (update-time) ───────────────────


class TestAssertCanAssignDesignatedUser:
    def test_assigning_to_yourself_needs_no_permission(self):
        assert_can_assign_designated_user(
            make_user(id=ACTOR_ID, permissions=[]), ACTOR_ID, "products"
        )

    def test_non_manager_cannot_assign_to_another_user(self):
        with pytest.raises(InsufficientPermissionsError):
            assert_can_assign_designated_user(writer(), OTHER_ID, "products")

    def test_manager_may_assign_to_another_user(self):
        assert_can_assign_designated_user(manager(), OTHER_ID, "products")

    def test_error_message_names_the_noun(self):
        with pytest.raises(InsufficientPermissionsError) as exc:
            assert_can_assign_designated_user(writer(), OTHER_ID, "projects")
        assert "projects" in str(exc.value)

    def test_rejects_before_considering_whether_the_target_exists(self):
        """The function never receives the user repo, permission is
        decided from the id alone, so a non-manager gets the same refusal
        for a real id and a nonexistent one. That is what stops the
        403/404 split leaking which user ids are real."""
        with pytest.raises(InsufficientPermissionsError):
            assert_can_assign_designated_user(writer(), 10**9, "products")


# ── The create/update asymmetry ───────────────────────────────────────


def test_same_request_is_forced_on_create_but_rejected_on_update():
    actor = writer()

    assert resolve_designated_user(actor, OTHER_ID) == ACTOR_ID  # silently forced
    with pytest.raises(InsufficientPermissionsError):  # loudly rejected
        assert_can_assign_designated_user(actor, OTHER_ID, "products")


# ── Both rules classes delegate here ──────────────────────────────────


@pytest.mark.parametrize("rules", [ProductRules, ProjectRules], ids=["Product", "Project"])
class TestRulesClassesDelegate:
    def test_resolve_matches_the_shared_helper(self, rules):
        assert rules.resolve_designated_user(writer(), OTHER_ID) == ACTOR_ID
        assert rules.resolve_designated_user(manager(), OTHER_ID) == OTHER_ID

    def test_assert_matches_the_shared_helper(self, rules):
        rules.assert_can_assign_designated_user(manager(), OTHER_ID)
        with pytest.raises(InsufficientPermissionsError):
            rules.assert_can_assign_designated_user(writer(), OTHER_ID)
