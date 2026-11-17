"""Who a product or project may be assigned to.

Create and update deliberately differ. On create, a caller without
MANAGE_PROJECTS silently gets the record assigned to themselves, since
there is nothing to reject yet. On update the same request is rejected,
because silently keeping the old owner would pretend the change succeeded.
The update check also stops create-then-PUT from bypassing the create rule.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


def resolve_designated_user(actor: User, designated_user_id: int | None) -> int:
    """The effective designated user: the actor themselves unless they hold
    manage:projects."""
    if not actor.has_permission(Permission.MANAGE_PROJECTS):
        return actor.id
    return designated_user_id or actor.id


def assert_can_assign_designated_user(actor: User, designated_user_id: int, noun: str) -> None:
    """Assigning to anyone but yourself needs manage:projects. Checked
    before the target user is looked up, so 403 versus 404 cannot probe
    which user ids exist.
    """
    if designated_user_id == actor.id:
        return
    assert_has_permission(actor, Permission.MANAGE_PROJECTS, "assign", f"{noun} to another user")
