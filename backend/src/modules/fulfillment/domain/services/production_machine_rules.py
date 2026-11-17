"""
Permission guards for ProductionMachine. No I/O. No ORM. No numbering, no
lifecycle status, a machine is a plain catalogue row with only an
`archived` flag, mirrors made_item_rules.py's simplest shape.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class ProductionMachineRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MACHINES, "create", "production machines")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MACHINES, "update", "production machines")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MACHINES, "archive", "production machines")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MACHINES, "restore", "production machines")
