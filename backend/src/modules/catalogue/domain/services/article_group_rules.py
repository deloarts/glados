"""
Business rules for the article group domain. No I/O. No ORM.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class ArticleGroupRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "create", "article groups")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "update", "article groups")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "archive", "article groups")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ARTICLE_GROUPS, "restore", "article groups")
