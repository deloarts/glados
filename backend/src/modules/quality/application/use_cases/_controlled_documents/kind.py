"""
Declares what differs between the kinds of controlled document (calculations,
checklists, sequences) as one `ControlledDocumentKind` per kind, so the use
cases in base.py are shared. The kind's domain rules class decides every permission
and state check; the kind here only adds what the application layer needs on
top: the result mappers, the live resource its events name and the one
revision choice that differs between kinds.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.platform.domain.entities.user import User
from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.quality.domain.services.controlled_document_rules import DocumentAccess

D = TypeVar("D", bound=ControlledDocument)
D_contra = TypeVar("D_contra", bound=ControlledDocument, contravariant=True)
R = TypeVar("R")
S = TypeVar("S")


class ControlledDocumentRules(Protocol[D_contra]):
    """The checks of a kind's domain rules class (CalculationRules,
    ChecklistRules) the shared use cases call. The class itself is passed,
    since its checks are static methods."""

    def assert_can_view(self, actor: User, document: D_contra, /) -> None: ...
    def assert_can_write(self, actor: User, action: str, /) -> None: ...
    def assert_can_update(self, actor: User, document: D_contra, /) -> None: ...
    def assert_can_delete_any(self, actor: User, /) -> None: ...
    def assert_can_delete(self, actor: User, document: D_contra, /) -> None: ...
    def assert_can_release_any(self, actor: User, /) -> None: ...
    def assert_can_release(self, actor: User, document: D_contra, /) -> None: ...
    def assert_can_manage(self, actor: User, action: str, /) -> None: ...
    def assert_can_mark_invalid(self, actor: User, document: D_contra, /) -> None: ...
    def assert_can_revise(self, actor: User, document: D_contra, /) -> None: ...


@dataclass(frozen=True)
class ControlledDocumentKind(Generic[D, R, S]):
    """One kind's declared shape. `access` is the kind's binding in
    controlled_document_rules.py and supplies its noun, its not found error
    and its manage permission. `title` reads the title events carry, which
    every kind has but the shared document entity does not declare.
    `takes_over_now` says whether a new revision supersedes the current one
    at once instead of on its release."""

    access: DocumentAccess
    rules: ControlledDocumentRules[D]
    live_resource: str
    to_result: Callable[[D], R]
    to_summary_result: Callable[[D], S]
    title: Callable[[D], str]
    takes_over_now: Callable[[D], bool]

    @property
    def label(self) -> str:
        """The capitalised noun, such as "Calculation"."""
        return self.access.noun.capitalize()
