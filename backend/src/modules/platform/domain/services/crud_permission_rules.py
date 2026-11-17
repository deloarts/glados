"""
Shared assert_can_create/update/delete permission-check helper for the
catalogue/master-data aggregates whose create/update/delete rules are
nothing more than "does the actor hold this permission". Aggregates with
real business logic beyond a permission check (e.g. ownership checks,
status-dependent rules) keep their own bespoke assert_can_* methods and do
not use this helper, see product_rules.py / customer_rules.py.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError


def assert_has_permission(actor: User, permission: str, action: str, noun: str) -> None:
    """Raise InsufficientPermissionsError unless actor holds `permission`.

    Message shape matches the convention used across catalogue/master-data
    rules classes: "User #{id} ({full_name}) cannot {action} {noun}."
    """
    if not actor.has_permission(permission):
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot {action} {noun}."
        )
