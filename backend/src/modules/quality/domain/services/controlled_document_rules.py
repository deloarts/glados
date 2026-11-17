"""
The access rules every kind of controlled document phrases the same way,
such as calculations and checklists: who may see one, the actor-only
permission gates, and the checks for the latest revision, the owner and
another user's draft. No I/O.

Each kind binds its permissions, its error classes and its noun into one
`DocumentAccess`, and its own rules class (calculation_rules.py,
checklist_rules.py) stays the public API that composes these with the
rules only that kind has. The state changes themselves live in
document_control.py.
"""

from dataclasses import dataclass
from typing import Protocol

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission


class IdentifiedDocument(Protocol):
    @property
    def id(self) -> int: ...


class OwnedDocument(IdentifiedDocument, Protocol):
    """The fields these rules read, which every controlled document that
    belongs to a project, a product or a single user has."""

    @property
    def creator_id(self) -> int: ...
    @property
    def revision(self) -> str: ...
    @property
    def is_latest(self) -> bool: ...
    @property
    def is_released(self) -> bool: ...
    @property
    def is_personal(self) -> bool: ...


@dataclass(frozen=True)
class DocumentAccess:
    """One kind's permissions, errors and noun. `noun` is the lowercase
    singular, such as "calculation"; messages capitalise it where a
    sentence starts with it."""

    noun: str
    write_permission: str
    release_permission: str
    manage_permission: str
    not_found_error: type[DomainError]
    owner_conflict_error: type[DomainError]
    not_latest_error: type[DomainError]
    already_released_error: type[DomainError]
    of_another_user_error: type[InsufficientPermissionsError]

    @property
    def plural(self) -> str:
        return f"{self.noun}s"

    def label(self, document: IdentifiedDocument) -> str:
        """Names the document in a message, such as "Calculation #12"."""
        return f"{self.noun.capitalize()} #{document.id}"

    def can_view(self, actor: User, document: OwnedDocument) -> bool:
        """A personal document is seen by its creator and by managers only;
        a project or product document by every logged-in user."""
        return (
            not document.is_personal
            or document.creator_id == actor.id
            or actor.has_permission(self.manage_permission)
        )

    def assert_can_view(self, actor: User, document: OwnedDocument) -> None:
        """Answers like a missing row, so another user's personal document
        stays invisible rather than forbidden."""
        if not self.can_view(actor, document):
            raise self.not_found_error(f"{self.label(document)} not found.")

    def assert_single_owner(self, project_id: int | None, product_id: int | None) -> None:
        if project_id is not None and product_id is not None:
            raise self.owner_conflict_error(
                f"A {self.noun} belongs to a project or to a product, not to both."
            )

    # The actor-only gates, checked before the document is loaded, so a
    # caller without the permission cannot tell an existing id from a
    # missing one.

    def assert_can_write(self, actor: User, action: str) -> None:
        assert_has_permission(actor, self.write_permission, action, self.plural)

    def assert_can_release_any(self, actor: User) -> None:
        assert_has_permission(actor, self.release_permission, "release", self.plural)

    def assert_can_manage(self, actor: User, action: str) -> None:
        assert_has_permission(actor, self.manage_permission, action, self.plural)

    def assert_can_delete_any(self, actor: User) -> None:
        if not (
            actor.has_permission(self.write_permission)
            or actor.has_permission(self.manage_permission)
        ):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot delete {self.plural}."
            )

    # The checks on a loaded document.

    def assert_not_released(self, document: OwnedDocument) -> None:
        if document.is_released:
            raise self.already_released_error(f"{self.label(document)} is already released.")

    def assert_latest(self, document: OwnedDocument, action: str) -> None:
        """`action` is the past participle, such as "deleted"."""
        if not document.is_latest:
            raise self.not_latest_error(
                f"Revision {document.revision} of {self.noun} #{document.id} is not the "
                f"latest revision and cannot be {action}."
            )

    def assert_own_or_manager(self, actor: User, document: OwnedDocument, action: str) -> None:
        if document.creator_id != actor.id and not actor.has_permission(self.manage_permission):
            raise self.of_another_user_error(
                f"User #{actor.id} ({actor.full_name}) cannot {action} {self.noun} "
                f"#{document.id}, it belongs to another user."
            )
