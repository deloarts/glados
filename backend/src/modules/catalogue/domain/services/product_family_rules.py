"""
Business rules for the product family domain. No I/O. No ORM. Product
families are catalogue master data of the same kind as article groups and
are managed with the article group permissions.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class ProductFamilyRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "create", "product families")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "update", "product families")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "archive", "product families")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "restore", "product families")
