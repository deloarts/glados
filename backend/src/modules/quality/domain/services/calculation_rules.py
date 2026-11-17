"""
Who may see, change, release and delete a saved calculation. No I/O.

Project and product calculations are visible to every logged-in user, a
personal one (no project, no product) only to its creator and to holders of
manage:calculations. Only the latest revision of a calculation can change,
and only while it is a draft; it is edited by its creator or a manager,
and only a draft is ever deleted.
Release needs release:calculations and may be done by the author. A new
revision starts from the released latest revision.

The checks every controlled document phrases the same way come from
controlled_document_rules.py; this class names the ones a calculation uses.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.errors import CalculationAlreadyReleasedError
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import CalculationNotLatestRevisionError
from src.modules.quality.domain.errors import CalculationNotReleasedError
from src.modules.quality.domain.errors import CalculationOfAnotherUserError
from src.modules.quality.domain.errors import CalculationOwnerConflictError
from src.modules.quality.domain.errors import CalculationReleasedError
from src.modules.quality.domain.services import document_control
from src.modules.quality.domain.services.controlled_document_rules import DocumentAccess

ACCESS = DocumentAccess(
    noun="calculation",
    write_permission=Permission.WRITE_CALCULATIONS,
    release_permission=Permission.RELEASE_CALCULATIONS,
    manage_permission=Permission.MANAGE_CALCULATIONS,
    not_found_error=CalculationNotFoundError,
    owner_conflict_error=CalculationOwnerConflictError,
    not_latest_error=CalculationNotLatestRevisionError,
    already_released_error=CalculationAlreadyReleasedError,
    of_another_user_error=CalculationOfAnotherUserError,
)


class CalculationRules:
    @staticmethod
    def can_view(actor: User, calculation: Calculation) -> bool:
        return ACCESS.can_view(actor, calculation)

    @staticmethod
    def assert_can_view(actor: User, calculation: Calculation) -> None:
        """Answers like a missing row, so another user's personal calculation
        stays invisible rather than forbidden."""
        ACCESS.assert_can_view(actor, calculation)

    @staticmethod
    def assert_valid_owner(project_id: int | None, product_id: int | None) -> None:
        ACCESS.assert_single_owner(project_id, product_id)

    @staticmethod
    def assert_can_create(actor: User) -> None:
        ACCESS.assert_can_write(actor, "create")

    # The actor-only parts of the rules below, checked before the calculation
    # is loaded, so a caller without the permission cannot tell an existing
    # id from a missing one.

    @staticmethod
    def assert_can_write(actor: User, action: str) -> None:
        ACCESS.assert_can_write(actor, action)

    @staticmethod
    def assert_can_release_any(actor: User) -> None:
        ACCESS.assert_can_release_any(actor)

    @staticmethod
    def assert_can_manage(actor: User, action: str) -> None:
        ACCESS.assert_can_manage(actor, action)

    @staticmethod
    def assert_can_delete_any(actor: User) -> None:
        ACCESS.assert_can_delete_any(actor)

    @staticmethod
    def assert_can_update(actor: User, calculation: Calculation) -> None:
        ACCESS.assert_can_write(actor, "update")
        ACCESS.assert_can_view(actor, calculation)
        if calculation.read_only:
            raise CalculationReleasedError(
                f"Calculation #{calculation.id} (revision {calculation.revision}) is "
                f"{'released' if calculation.is_latest else 'superseded'} and cannot be "
                "changed; start a new revision or save a copy instead."
            )
        ACCESS.assert_own_or_manager(actor, calculation, "update")

    @staticmethod
    def assert_can_delete(actor: User, calculation: Calculation) -> None:
        ACCESS.assert_can_view(actor, calculation)
        ACCESS.assert_latest(calculation, "deleted")
        document_control.assert_deletable(calculation, ACCESS.label(calculation))
        ACCESS.assert_can_write(actor, "delete")
        ACCESS.assert_own_or_manager(actor, calculation, "delete")

    @staticmethod
    def assert_can_release(actor: User, calculation: Calculation) -> None:
        ACCESS.assert_can_release_any(actor)
        ACCESS.assert_can_view(actor, calculation)
        ACCESS.assert_not_released(calculation)
        ACCESS.assert_latest(calculation, "released")

    @staticmethod
    def assert_can_mark_invalid(actor: User, calculation: Calculation) -> None:
        ACCESS.assert_can_manage(actor, "mark invalid")
        ACCESS.assert_can_view(actor, calculation)
        document_control.assert_can_be_marked_invalid(calculation, ACCESS.label(calculation))

    @staticmethod
    def assert_can_revise(actor: User, calculation: Calculation) -> None:
        ACCESS.assert_can_write(actor, "revise")
        ACCESS.assert_can_view(actor, calculation)
        ACCESS.assert_latest(calculation, "revised")
        if not calculation.is_released:
            raise CalculationNotReleasedError(
                f"Calculation #{calculation.id} must be released before a new revision is "
                "started; a draft is changed in place."
            )
