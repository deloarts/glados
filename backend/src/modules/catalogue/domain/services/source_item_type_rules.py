"""
Business rules for the source item type domain. No I/O. No ORM.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class SourceItemTypeRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_SOURCE_ITEM_TYPES, "create", "source item types"
        )

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_SOURCE_ITEM_TYPES, "update", "source item types"
        )

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_SOURCE_ITEM_TYPES, "archive", "source item types"
        )

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_SOURCE_ITEM_TYPES, "restore", "source item types"
        )
