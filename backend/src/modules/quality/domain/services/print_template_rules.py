"""
Permission guards for PrintTemplate. Settings-style resource: only update
(and its reset-to-default variant) need a permission check, reads are open
to any active user same as everywhere else in this codebase.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class PrintTemplateRules:
    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PRINTERS, "update", "print templates")
