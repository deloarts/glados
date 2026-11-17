"""
Pure business rules for customer operations. No I/O.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class CustomerRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PROJECTS, "create", "customers")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PROJECTS, "update", "customers")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_PROJECTS, "archive", "customers")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_PROJECTS, "restore", "customers")
