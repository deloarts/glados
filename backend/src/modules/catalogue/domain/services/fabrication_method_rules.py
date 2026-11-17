"""
Business rules for the fabrication method domain. No I/O. No ORM.
"""

from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class FabricationMethodRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_FABRICATION_METHODS, "create", "fabrication methods"
        )

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_FABRICATION_METHODS, "update", "fabrication methods"
        )

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_FABRICATION_METHODS, "archive", "fabrication methods"
        )

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_FABRICATION_METHODS, "restore", "fabrication methods"
        )

    @staticmethod
    def assert_can_be_assembly_default(fabrication_method: FabricationMethod) -> None:
        """An archived method is hidden from pickers, so it cannot be the
        method preselected for assemblies."""
        if fabrication_method.archived:
            raise FabricationMethodArchivedError(
                f"Fabrication method #{fabrication_method.id} is archived and cannot be "
                "the default for assemblies."
            )
