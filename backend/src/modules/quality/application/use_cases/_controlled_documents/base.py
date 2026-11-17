"""
Generic use-case core behind the document control actions of every kind of
controlled document: delete the latest draft, take and end the edit lock,
release, mark invalid, start a revision and read one or its revisions. The
flows are the same for every kind, with the same permission order, events,
log texts and commit points; only the types, the rules class and a few
names differ, which the kind's `ControlledDocumentKind` declares.

Each concrete use case (DeleteCalculation, LockChecklist, ...) is a small
subclass that binds `_kind` and keeps its own constructor and `execute`
signature, because endpoints, deps and tests call them with keywords that
name the kind (`calculation_repo`, `checklist_id`). Its `execute` calls the
matching step here.

Every step checks the actor-only permission before the document is loaded,
then the document rules, publishes its events before the unit of work
commits, and logs after the commit. A step that changes the document loads
it under the row lock of its lineage (`get_for_update`), so the checks it
makes still hold when it writes.
"""

from typing import Generic
from uuid import UUID

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.controlled_document_dto import LockCommand
from src.modules.quality.application.dto.controlled_document_dto import MarkInvalidCommand
from src.modules.quality.application.services import controlled_documents
from src.modules.quality.application.use_cases._controlled_documents.kind import (
    ControlledDocumentKind,
)
from src.modules.quality.application.use_cases._controlled_documents.kind import D
from src.modules.quality.application.use_cases._controlled_documents.kind import R
from src.modules.quality.application.use_cases._controlled_documents.kind import S
from src.modules.quality.domain.events.document_events import DocumentEditingEnded
from src.modules.quality.domain.events.document_events import DocumentEditingTakenOver
from src.modules.quality.domain.events.document_events import DocumentMarkedInvalid
from src.modules.quality.domain.events.document_events import DocumentRevised
from src.modules.quality.domain.services import document_control
from src.modules.quality.ports.outbound.repositories.controlled_document_repository import (
    IControlledDocumentRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


class _ControlledDocumentUseCase(Generic[D, R, S]):
    _kind: ControlledDocumentKind[D, R, S]

    def __init__(self, repo: IControlledDocumentRepository[D]) -> None:
        self._documents = repo

    async def _load(self, document_id: int, *, for_update: bool = False) -> D:
        if for_update:
            document = await self._documents.get_for_update(document_id)
        else:
            document = await self._documents.get_by_id(document_id)
        if document is None:
            raise self._kind.access.not_found_error(f"{self._kind.label} #{document_id} not found.")
        return document


# ── Reads ─────────────────────────────────────────────────────────────


class GetControlledDocument(_ControlledDocumentUseCase[D, R, S]):
    async def _get(self, actor: User, document_id: int) -> R:
        document = await self._load(document_id)
        self._kind.rules.assert_can_view(actor, document)
        return self._kind.to_result(document)


class GetControlledDocumentByPublicId(_ControlledDocumentUseCase[D, R, S]):
    async def _get(self, actor: User, public_id: UUID) -> R:
        document = await self._documents.get_by_public_id(public_id)
        if document is None:
            raise self._kind.access.not_found_error(f"{self._kind.label} {public_id} not found.")
        self._kind.rules.assert_can_view(actor, document)
        return self._kind.to_result(document)


class GetControlledDocumentRevisions(_ControlledDocumentUseCase[D, R, S]):
    """Every revision of the document's lineage, newest first. Revisions
    share their owner, so seeing one means seeing all."""

    async def _get(self, actor: User, document_id: int) -> list[S]:
        document = await self._load(document_id)
        self._kind.rules.assert_can_view(actor, document)
        lineage = await self._documents.get_lineage(document.lineage)
        return [self._kind.to_summary_result(revision) for revision in lineage]


# ── Delete ────────────────────────────────────────────────────────────


class DeleteControlledDocument(_ControlledDocumentUseCase[D, R, S]):
    """Deletes the latest revision for good, as long as it is a draft. The
    revision before it, if any, becomes the latest and valid one again."""

    def __init__(self, repo: IControlledDocumentRepository[D], *, uow: IUnitOfWork) -> None:
        super().__init__(repo)
        self._uow = uow

    async def _delete(self, actor: User, document_id: int) -> None:
        self._kind.rules.assert_can_delete_any(actor)
        document = await self._load(document_id, for_update=True)
        self._kind.rules.assert_can_delete(actor, document)
        await controlled_documents.delete_latest(self._documents, document, actor)
        await self._uow.commit()
        log.info(f"{self._kind.label} #%s deleted by user #%s.", document_id, actor.id)


# ── Edit lock ─────────────────────────────────────────────────────────


class _WithEvents(_ControlledDocumentUseCase[D, R, S]):
    def __init__(
        self, repo: IControlledDocumentRepository[D], event_bus: IEventBus, *, uow: IUnitOfWork
    ) -> None:
        super().__init__(repo)
        self._bus = event_bus
        self._uow = uow


class LockControlledDocument(_WithEvents[D, R, S]):
    """Takes the edit lock, or renews the one the actor holds. Taking it
    over from another editor needs the kind's manage permission, and that
    editor is notified."""

    async def _lock(self, actor: User, document_id: int, cmd: LockCommand) -> R:
        kind = self._kind
        kind.rules.assert_can_write(actor, "edit")
        document = await self._load(document_id, for_update=True)
        kind.rules.assert_can_update(actor, document)
        saved, previous = await controlled_documents.lock(
            self._documents,
            document,
            actor,
            label=kind.access.label(document),
            take_over=cmd.take_over,
            may_take_over=actor.has_permission(kind.access.manage_permission),
        )
        if previous is not None:
            await self._bus.publish(
                DocumentEditingTakenOver(
                    resource=kind.live_resource,
                    document_id=saved.id,
                    title=kind.title(saved),
                    previous_editor_id=previous,
                    actor_id=actor.id,
                    actor_name=actor.full_name,
                )
            )
        await self._uow.commit()
        if previous is not None:
            log.info(
                f"Editing of {kind.access.noun} #%s taken over from user #%s by user #%s.",
                saved.id,
                previous,
                actor.id,
            )
        return kind.to_result(saved)


class UnlockControlledDocument(_WithEvents[D, R, S]):
    """Ends the actor's own edit lock, or with `force` someone else's,
    which needs the kind's manage permission; that editor is notified."""

    async def _unlock(self, actor: User, document_id: int, *, force: bool) -> R:
        kind = self._kind
        document = await self._load(document_id, for_update=True)
        kind.rules.assert_can_view(actor, document)
        saved, previous = await controlled_documents.end_lock(
            self._documents,
            document,
            actor,
            force=force,
            may_force=actor.has_permission(kind.access.manage_permission),
        )
        if previous is not None:
            await self._bus.publish(
                DocumentEditingEnded(
                    resource=kind.live_resource,
                    document_id=saved.id,
                    title=kind.title(saved),
                    previous_editor_id=previous,
                    actor_id=actor.id,
                    actor_name=actor.full_name,
                )
            )
        await self._uow.commit()
        if previous is not None:
            log.info(
                f"Editing of {kind.access.noun} #%s by user #%s ended by user #%s.",
                saved.id,
                previous,
                actor.id,
            )
        return kind.to_result(saved)


# ── Release and invalid marking ───────────────────────────────────────


class ReleaseControlledDocument(_ControlledDocumentUseCase[D, R, S]):
    """Releases the latest revision and supersedes the one before it. Who
    may release which revision is the kind's rules' decision."""

    def __init__(self, repo: IControlledDocumentRepository[D], *, uow: IUnitOfWork) -> None:
        super().__init__(repo)
        self._uow = uow

    async def _release(self, actor: User, document_id: int) -> R:
        kind = self._kind
        kind.rules.assert_can_release_any(actor)
        document = await self._load(document_id, for_update=True)
        kind.rules.assert_can_release(actor, document)
        document_control.assert_not_locked_by_other(
            document, actor, now_utc(), kind.access.label(document)
        )
        saved = await controlled_documents.release(self._documents, document, actor)
        await self._uow.commit()
        log.info(f"{kind.label} #%s released by user #%s.", saved.id, actor.id)
        return kind.to_result(saved)


class MarkControlledDocumentInvalid(_WithEvents[D, R, S]):
    """Marks a released revision invalid with a reason and tells everyone
    who worked on the document."""

    async def _mark_invalid(self, actor: User, document_id: int, cmd: MarkInvalidCommand) -> R:
        kind = self._kind
        kind.rules.assert_can_manage(actor, "mark invalid")
        document = await self._load(document_id, for_update=True)
        kind.rules.assert_can_mark_invalid(actor, document)
        saved = await controlled_documents.mark_invalid(
            self._documents, document, actor, cmd.reason
        )
        await self._bus.publish(
            DocumentMarkedInvalid(
                resource=kind.live_resource,
                document_id=saved.id,
                title=kind.title(saved),
                revision=saved.revision,
                reason=saved.invalid_reason or "",
                actor_id=actor.id,
                actor_name=actor.full_name,
                recipient_ids=await controlled_documents.people_of(self._documents, saved),
            )
        )
        await self._uow.commit()
        log.info(f"{kind.label} #%s marked invalid by user #%s.", saved.id, actor.id)
        return kind.to_result(saved)


# ── Revisions ─────────────────────────────────────────────────────────


class ReviseControlledDocument(_ControlledDocumentUseCase[D, R, S]):
    """Starts the next revision of the latest one as a draft with the same
    content. Whether the current revision is superseded at once or only on
    the new one's release is the kind's `takes_over_now`."""

    def __init__(
        self,
        repo: IControlledDocumentRepository[D],
        admin_settings_repo: IFulfillmentSettingsRepository,
        event_bus: IEventBus,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(repo)
        self._admin_settings = admin_settings_repo
        self._bus = event_bus
        self._uow = uow

    async def _revise(self, actor: User, document_id: int, reason: str) -> R:
        kind = self._kind
        kind.rules.assert_can_write(actor, "revise")
        current = await self._load(document_id, for_update=True)
        kind.rules.assert_can_revise(actor, current)
        saved = await controlled_documents.start_revision(
            self._documents,
            self._admin_settings,
            current,
            actor,
            reason=reason,
            takes_over_now=kind.takes_over_now(current),
        )
        await self._bus.publish(
            DocumentRevised(
                resource=kind.live_resource,
                document_id=saved.id,
                title=kind.title(saved),
                revision=saved.revision,
                previous_revision=current.revision,
                reason=saved.revision_reason or "",
                actor_id=actor.id,
                actor_name=actor.full_name,
                recipient_ids=await controlled_documents.people_of(self._documents, saved),
            )
        )
        await self._uow.commit()
        log.info(
            f"{kind.label} #%s revision %s created as #%s by user #%s.",
            current.id,
            saved.revision,
            saved.id,
            actor.id,
        )
        return kind.to_result(saved)
