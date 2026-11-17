"""
Pure business rules for project operations. No I/O.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.designated_user_rules import (
    assert_can_assign_designated_user as _assert_can_assign_designated_user,
)
from src.modules.platform.domain.services.designated_user_rules import (
    resolve_designated_user as _resolve_designated_user,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project


class ProjectRules:
    # ── Create ────────────────────────────────────────────────────────

    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PROJECTS, "create", "projects")

    @staticmethod
    def resolve_designated_user(actor: User, designated_user_id: int | None) -> int:
        """Create-time resolution, see designated_user_rules.py."""
        return _resolve_designated_user(actor, designated_user_id)

    @staticmethod
    def assert_can_assign_designated_user(actor: User, designated_user_id: int) -> None:
        """Update-time counterpart: rejects instead of silently
        rewriting. See designated_user_rules.py."""
        _assert_can_assign_designated_user(actor, designated_user_id, "projects")

    # ── Update ────────────────────────────────────────────────────────

    @staticmethod
    def assert_can_update(actor: User, project: Project) -> None:
        """
        Users with manage:projects OR the designated user of the project may update it.
        """
        if (
            not actor.has_permission(Permission.MANAGE_PROJECTS)
            and actor.id != project.designated_user_id
        ):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.username!r}) cannot update "
                f"project #{project.id} ({project.project_number!r}): insufficient permissions."
            )

    @staticmethod
    def assert_can_move_status(actor: User) -> None:
        """A status move (hold, resume, complete, archive, reopen) needs
        manage:projects; the designated user edits the rest of the project
        but does not move its status."""
        assert_has_permission(actor, Permission.MANAGE_PROJECTS, "change the status of", "projects")

    # ── Delete ────────────────────────────────────────────────────────

    @staticmethod
    def assert_can_delete(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_PROJECTS, "delete", "projects")
