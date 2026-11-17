"""
Who may see, change, revise, release and delete a checklist. No I/O.

A checklist belongs to the kinds of owner its type allows (see
checklist_type.py). Project and product checklists are visible to every
logged-in user, a personal one only to its creator and to holders of
manage:checklists. Only the latest revision of a checklist can change, and
only while it is not released. A draft is edited by its creator or a
manager, and only a draft is ever deleted.

A checklist is finished when every item is answered and every finding has
a remark; for a type that requires a release it is finished only once
released. The release is a second person's sign-off: it needs
release:checklists and is never given by the creator of that revision. A
new revision starts from a finished latest revision.

The checks every controlled document phrases the same way come from
controlled_document_rules.py; this class names the ones a checklist uses
and adds its own.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.errors import ChecklistAlreadyReleasedError
from src.modules.quality.domain.errors import ChecklistIncompleteError
from src.modules.quality.domain.errors import ChecklistNotFoundError
from src.modules.quality.domain.errors import ChecklistNotLatestRevisionError
from src.modules.quality.domain.errors import ChecklistOfAnotherUserError
from src.modules.quality.domain.errors import ChecklistOwnerConflictError
from src.modules.quality.domain.errors import ChecklistOwnerNotAllowedError
from src.modules.quality.domain.errors import ChecklistOwnReleaseError
from src.modules.quality.domain.errors import ChecklistReadOnlyError
from src.modules.quality.domain.errors import ChecklistReleaseNotApplicableError
from src.modules.quality.domain.services import document_control
from src.modules.quality.domain.services.checklist_evaluation import findings_without_remark
from src.modules.quality.domain.services.controlled_document_rules import DocumentAccess
from src.modules.quality.domain.value_objects.checklist_type import ChecklistOwnerKind
from src.modules.quality.domain.value_objects.checklist_type import ChecklistTypeSpec

ACCESS = DocumentAccess(
    noun="checklist",
    write_permission=Permission.WRITE_CHECKLISTS,
    release_permission=Permission.RELEASE_CHECKLISTS,
    manage_permission=Permission.MANAGE_CHECKLISTS,
    not_found_error=ChecklistNotFoundError,
    owner_conflict_error=ChecklistOwnerConflictError,
    not_latest_error=ChecklistNotLatestRevisionError,
    already_released_error=ChecklistAlreadyReleasedError,
    of_another_user_error=ChecklistOfAnotherUserError,
)


class ChecklistRules:
    @staticmethod
    def can_view(actor: User, checklist: Checklist) -> bool:
        return ACCESS.can_view(actor, checklist)

    @staticmethod
    def assert_can_view(actor: User, checklist: Checklist) -> None:
        """Answers like a missing row, so another user's personal checklist
        stays invisible rather than forbidden."""
        ACCESS.assert_can_view(actor, checklist)

    @staticmethod
    def assert_valid_owner(
        spec: ChecklistTypeSpec, project_id: int | None, product_id: int | None
    ) -> None:
        ACCESS.assert_single_owner(project_id, product_id)
        kind: ChecklistOwnerKind = (
            "project"
            if project_id is not None
            else "product"
            if product_id is not None
            else "personal"
        )
        if not spec.allows_owner(kind):
            allowed = ", ".join(sorted(spec.owner_kinds))
            raise ChecklistOwnerNotAllowedError(
                f"A {spec.slug} checklist cannot have the owner kind {kind!r}; allowed: {allowed}."
            )

    @staticmethod
    def assert_can_create(actor: User) -> None:
        ACCESS.assert_can_write(actor, "create")

    # The actor-only parts of the rules below, checked before the checklist
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
    def assert_can_update(actor: User, checklist: Checklist) -> None:
        ACCESS.assert_can_write(actor, "update")
        ACCESS.assert_can_view(actor, checklist)
        if checklist.read_only:
            raise ChecklistReadOnlyError(
                f"Checklist #{checklist.id} (revision {checklist.revision}) is "
                f"{'released' if checklist.is_released else 'superseded'} and cannot be "
                "changed; start a new revision instead."
            )
        ACCESS.assert_own_or_manager(actor, checklist, "update")

    @staticmethod
    def assert_can_delete(actor: User, checklist: Checklist) -> None:
        ACCESS.assert_can_view(actor, checklist)
        ACCESS.assert_latest(checklist, "deleted")
        document_control.assert_deletable(checklist, ACCESS.label(checklist))
        ACCESS.assert_can_write(actor, "delete")
        ACCESS.assert_own_or_manager(actor, checklist, "delete")

    @staticmethod
    def assert_can_release(actor: User, checklist: Checklist) -> None:
        ACCESS.assert_can_release_any(actor)
        ACCESS.assert_can_view(actor, checklist)
        if not checklist.release_required:
            raise ChecklistReleaseNotApplicableError(
                f"Checklists of type {checklist.type!r} are not released."
            )
        ACCESS.assert_not_released(checklist)
        ACCESS.assert_latest(checklist, "released")
        if checklist.creator_id == actor.id:
            raise ChecklistOwnReleaseError(
                f"User #{actor.id} ({actor.full_name}) created revision {checklist.revision} "
                f"of checklist #{checklist.id} and cannot release it; another person must."
            )
        ChecklistRules.assert_complete(checklist)

    @staticmethod
    def assert_can_mark_invalid(actor: User, checklist: Checklist) -> None:
        ACCESS.assert_can_manage(actor, "mark invalid")
        ACCESS.assert_can_view(actor, checklist)
        document_control.assert_can_be_marked_invalid(checklist, ACCESS.label(checklist))

    @staticmethod
    def assert_can_revise(actor: User, checklist: Checklist) -> None:
        ACCESS.assert_can_write(actor, "revise")
        ACCESS.assert_can_view(actor, checklist)
        ACCESS.assert_latest(checklist, "revised")
        if checklist.release_required:
            if not checklist.is_released:
                raise ChecklistIncompleteError(
                    f"Checklist #{checklist.id} must be released before a new revision is started."
                )
            return
        ChecklistRules.assert_complete(checklist)

    @staticmethod
    def is_finished(checklist: Checklist) -> bool:
        if checklist.release_required:
            return checklist.is_released
        return checklist.is_complete and not findings_without_remark(
            checklist.answers, checklist.remarks
        )

    @staticmethod
    def assert_complete(checklist: Checklist) -> None:
        if not checklist.is_complete:
            open_count = checklist.item_count - checklist.answered_count
            raise ChecklistIncompleteError(
                f"Checklist #{checklist.id} has {open_count} unanswered item(s)."
            )
        missing = findings_without_remark(checklist.answers, checklist.remarks)
        if missing:
            raise ChecklistIncompleteError(
                f"Checklist #{checklist.id} has {len(missing)} finding(s) without a remark, "
                f"e.g. {missing[:3]}."
            )
