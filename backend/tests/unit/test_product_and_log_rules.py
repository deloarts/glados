"""
Direct tests for two permission-rule modules:
src/modules/workspace/domain/services/product_rules.py and
src/modules/platform/domain/services/log_rules.py. product_rules.py is deliberately NOT
folded into crud_permission_rules.py (it has real behavioral differences:
a designated-user concept and an owner-or-manage update check), so it
needs its own tests rather than inheriting the shared helper's.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.log_rules import LogRules
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.services.product_rules import ProductRules
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_product(id: int = 1, designated_user_id: int = 1) -> Product:
    return Product(
        id=id,
        created=datetime.now(UTC),
        designated_user_id=designated_user_id,
        product_number="P-001",
    )


# ── ProductRules.assert_can_create ────────────────────────────────────


class TestProductRulesCreate:
    def test_with_write_projects_permission(self):
        ProductRules.assert_can_create(make_user(permissions=[Permission.WRITE_PROJECTS]))

    def test_without_permission_raises(self):
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_create(make_user(permissions=[]))

    def test_manage_projects_alone_is_not_enough_to_create(self):
        """assert_can_create checks WRITE_PROJECTS specifically, MANAGE
        is about acting on *others'* products, not a superset grant."""
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_create(make_user(permissions=[Permission.MANAGE_PROJECTS]))


# ── ProductRules.resolve_designated_user ──────────────────────────────


class TestProductRulesResolveDesignatedUser:
    def test_without_manage_permission_always_returns_the_actor(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_PROJECTS])
        assert ProductRules.resolve_designated_user(actor, designated_user_id=99) == 7

    def test_without_manage_permission_ignores_none_too(self):
        actor = make_user(id=7, permissions=[])
        assert ProductRules.resolve_designated_user(actor, designated_user_id=None) == 7

    def test_with_manage_permission_honours_the_requested_user(self):
        actor = make_user(id=7, permissions=[Permission.MANAGE_PROJECTS])
        assert ProductRules.resolve_designated_user(actor, designated_user_id=99) == 99

    def test_with_manage_permission_falls_back_to_actor_when_none(self):
        actor = make_user(id=7, permissions=[Permission.MANAGE_PROJECTS])
        assert ProductRules.resolve_designated_user(actor, designated_user_id=None) == 7

    def test_with_manage_permission_falls_back_to_actor_on_zero(self):
        """0 is falsy, so `designated_user_id or actor.id` treats it as
        unset rather than as user #0."""
        actor = make_user(id=7, permissions=[Permission.MANAGE_PROJECTS])
        assert ProductRules.resolve_designated_user(actor, designated_user_id=0) == 7


# ── ProductRules.assert_can_update ────────────────────────────────────


class TestProductRulesUpdate:
    def test_designated_user_can_update_own_product_without_manage(self):
        actor = make_user(id=7, permissions=[])
        ProductRules.assert_can_update(actor, make_product(designated_user_id=7))

    def test_manager_can_update_another_users_product(self):
        actor = make_user(id=7, permissions=[Permission.MANAGE_PROJECTS])
        ProductRules.assert_can_update(actor, make_product(designated_user_id=99))

    def test_non_manager_cannot_update_another_users_product(self):
        actor = make_user(id=7, permissions=[Permission.WRITE_PROJECTS])
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_update(actor, make_product(designated_user_id=99))


# ── ProductRules.assert_can_archive / assert_can_restore ───────────────


class TestProductRulesArchive:
    def test_with_manage_permission(self):
        ProductRules.assert_can_archive(make_user(permissions=[Permission.MANAGE_PROJECTS]))

    def test_write_permission_alone_cannot_archive(self):
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_archive(make_user(permissions=[Permission.WRITE_PROJECTS]))

    def test_without_any_permission_raises(self):
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_archive(make_user(permissions=[]))


class TestProductRulesRestore:
    def test_with_manage_permission(self):
        ProductRules.assert_can_restore(make_user(permissions=[Permission.MANAGE_PROJECTS]))

    def test_write_permission_alone_cannot_restore(self):
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_restore(make_user(permissions=[Permission.WRITE_PROJECTS]))

    def test_without_any_permission_raises(self):
        with pytest.raises(InsufficientPermissionsError):
            ProductRules.assert_can_restore(make_user(permissions=[]))


# ── LogRules ──────────────────────────────────────────────────────────


class TestLogRules:
    def test_with_read_settings_permission(self):
        LogRules.assert_can_read(make_user(permissions=[Permission.READ_SETTINGS]))

    def test_without_permission_raises(self):
        with pytest.raises(InsufficientPermissionsError):
            LogRules.assert_can_read(make_user(permissions=[]))

    def test_system_user_bypasses_the_check(self):
        actor = make_user(permissions=[])
        actor.is_systemuser = True
        LogRules.assert_can_read(actor)
