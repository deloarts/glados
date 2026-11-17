"""
Business rules for log access. No I/O. No ORM.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class LogRules:
    @staticmethod
    def assert_can_read(actor: User) -> None:
        assert_has_permission(actor, Permission.READ_SETTINGS, "read", "logs")
