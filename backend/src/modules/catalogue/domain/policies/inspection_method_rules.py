"""
Business rules for the inspection method domain. No I/O. No ORM.
"""

from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class InspectionMethodRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_INSPECTION_METHODS, "create", "inspection methods"
        )

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_INSPECTION_METHODS, "update", "inspection methods"
        )

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_INSPECTION_METHODS, "archive", "inspection methods"
        )

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_INSPECTION_METHODS, "restore", "inspection methods"
        )


def seed_inspection_estimates(
    method: InspectionMethod,
    setup_minutes: int | None,
    minutes_per_piece: float | None,
) -> tuple[int | None, float | None]:
    """The durations a step or process created against `method` should
    start life with: whatever the caller supplied, falling back to the
    method's own defaults.

    Seeding happens at creation only. Editing a method must never
    retro-apply to existing steps: someone who tuned a step's estimate by
    hand would otherwise see it silently revert. Both sides are optional:
    a method with no defaults leaves the step with no estimate, which
    production_order_rules.estimate_time_source reports as
    "not_applicable" rather than flagging it as missing forever."""
    return (
        setup_minutes if setup_minutes is not None else method.default_setup_minutes,
        minutes_per_piece if minutes_per_piece is not None else method.default_minutes_per_piece,
    )
