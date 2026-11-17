"""
Domain events of controlled documents, such as calculations and checklists.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class DocumentEditingTakenOver(DomainEvent):
    """A manager took the edit lock of a draft from the person editing it,
    whose unsaved changes are then lost."""

    # The live resource of the document, such as "calculations".
    resource: str
    document_id: int
    title: str
    previous_editor_id: int
    actor_id: int
    actor_name: str


@dataclass(frozen=True)
class DocumentEditingEnded(DomainEvent):
    """A manager ended someone else's edit lock without taking it, so the
    draft is free again; the editor's unsaved changes are lost."""

    resource: str
    document_id: int
    title: str
    previous_editor_id: int
    actor_id: int
    actor_name: str


@dataclass(frozen=True)
class DocumentMarkedInvalid(DomainEvent):
    """A released revision was marked invalid. Its creator and everyone who
    worked on the document are told, since copies of it may be in use."""

    resource: str
    document_id: int
    title: str
    revision: str
    reason: str
    actor_id: int
    actor_name: str
    recipient_ids: list[int]


@dataclass(frozen=True)
class DocumentRevised(DomainEvent):
    """A new revision of a document was started; the people who worked on
    the earlier revisions are told."""

    resource: str
    document_id: int
    title: str
    revision: str
    previous_revision: str
    reason: str
    actor_id: int
    actor_name: str
    recipient_ids: list[int]
