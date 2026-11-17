"""
Creates checklists and updates the latest, unreleased revision of one. The
header, answers and remarks are stored as the frontend sent them; the
backend checks the answer values and recomputes the counts and the verdict.
A new checklist starts at the revision the admin settings name as the
first one, the same start value made items use, and gets the next document
number of the checklist numbering format. An update is saved only by
the holder of the edit lock, who is then remembered as one of its editors.
"""

from dataclasses import replace
from functools import partial
from uuid import uuid4

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.checklist_dto import ChecklistResult
from src.modules.quality.application.dto.checklist_dto import CreateChecklistCommand
from src.modules.quality.application.dto.checklist_dto import UpdateChecklistCommand
from src.modules.quality.application.mappers.checklist_mapper import ChecklistMapper
from src.modules.quality.application.services import controlled_documents
from src.modules.quality.domain.entities.checklist import Checklist
from src.modules.quality.domain.errors import ChecklistNotFoundError
from src.modules.quality.domain.errors import ChecklistOwnerLockedError
from src.modules.quality.domain.errors import ChecklistTypeUnknownError
from src.modules.quality.domain.services import document_control
from src.modules.quality.domain.services.checklist_evaluation import evaluate
from src.modules.quality.domain.services.checklist_rules import ChecklistRules
from src.modules.quality.domain.value_objects.checklist_type import ChecklistTypeSpec
from src.modules.quality.domain.value_objects.checklist_type import checklist_type_spec
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc


class _ChecklistWriter:
    def __init__(
        self,
        checklist_repo: IChecklistRepository,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._checklists = checklist_repo
        self._projects = project_repo
        self._products = product_repo
        self._uow = uow

    async def _assert_owner_exists(
        self, spec: ChecklistTypeSpec, project_id: int | None, product_id: int | None
    ) -> None:
        """Checks that the owner is one the checklist type allows and that it
        exists."""
        await controlled_documents.assert_owner_exists(
            self._projects,
            self._products,
            project_id,
            product_id,
            valid_owner=partial(ChecklistRules.assert_valid_owner, spec),
            plural="checklists",
        )


class CreateChecklist(_ChecklistWriter):
    def __init__(
        self,
        checklist_repo: IChecklistRepository,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        admin_settings_repo: IFulfillmentSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(checklist_repo, project_repo, product_repo, uow=uow)
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User, cmd: CreateChecklistCommand) -> ChecklistResult:
        ChecklistRules.assert_can_create(actor)
        spec = checklist_type_spec(cmd.type)
        if spec is None:
            raise ChecklistTypeUnknownError(f"Unknown checklist type {cmd.type!r}.")
        await self._assert_owner_exists(spec, cmd.project_id, cmd.product_id)
        evaluation = evaluate(cmd.answers, cmd.item_count)
        settings = await self._admin_settings.get_made_items()

        now = now_utc()
        checklist = Checklist(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Checklist created."),
            type=cmd.type,
            title=cmd.title,
            header=cmd.header,
            answers=cmd.answers,
            remarks=cmd.remarks,
            definition_version=cmd.definition_version,
            item_count=cmd.item_count,
            answered_count=evaluation.answered_count,
            finding_count=evaluation.finding_count,
            verdict=evaluation.verdict,
            project_id=cmd.project_id,
            product_id=cmd.product_id,
            lineage=uuid4(),
            revision=settings.revision_start,
            revision_reason=None,
            is_latest=True,
            superseded_at=None,
            creator_id=actor.id,
            released_at=None,
            released_by_id=None,
        )

        async def write() -> Checklist:
            number = await self._checklists.next_document_number(settings.checklist_number_format)
            return await self._checklists.save(replace(checklist, document_number=number))

        saved = await commit_with_number_retry(self._uow, write)
        log.info("Checklist #%s (%s) created by user #%s.", saved.id, saved.type, actor.id)
        return ChecklistMapper.to_result(saved)


class UpdateChecklist(_ChecklistWriter):
    async def execute(
        self, actor: User, checklist_id: int, cmd: UpdateChecklistCommand
    ) -> ChecklistResult:
        ChecklistRules.assert_can_write(actor, "update")
        checklist = found_or_raise(
            await self._checklists.get_for_update(checklist_id),
            ChecklistNotFoundError,
            f"Checklist #{checklist_id} not found.",
        )
        ChecklistRules.assert_can_update(actor, checklist)
        now = now_utc()
        document_control.assert_holds_lock(checklist, actor, now, f"Checklist #{checklist.id}")
        document_control.renew_lock(checklist, actor, now)
        document_control.record_editor(checklist, actor)
        if (cmd.project_id, cmd.product_id) != (checklist.project_id, checklist.product_id):
            if len(await self._checklists.get_lineage(checklist.lineage)) > 1:
                raise ChecklistOwnerLockedError(
                    f"Checklist #{checklist.id} has earlier revisions; its owner cannot change."
                )
            spec = checklist_type_spec(checklist.type)
            if spec is None:
                raise ChecklistTypeUnknownError(f"Unknown checklist type {checklist.type!r}.")
            await self._assert_owner_exists(spec, cmd.project_id, cmd.product_id)
        evaluation = evaluate(cmd.answers, cmd.item_count)

        old = self._snapshot(checklist)
        checklist.title = cmd.title
        checklist.definition_version = cmd.definition_version
        checklist.item_count = cmd.item_count
        checklist.project_id = cmd.project_id
        checklist.product_id = cmd.product_id
        checklist.answered_count = evaluation.answered_count
        checklist.finding_count = evaluation.finding_count
        checklist.verdict = evaluation.verdict
        new = self._snapshot(checklist)

        lines = [diff_changes(old, new, heading="Checklist updated:")]
        if cmd.header != checklist.header:
            lines.append("Header changed.")
        if cmd.answers != checklist.answers:
            lines.append("Answers changed.")
        if cmd.remarks != checklist.remarks:
            lines.append("Remarks changed.")
        checklist.header = cmd.header
        checklist.answers = cmd.answers
        checklist.remarks = cmd.remarks
        checklist.changed = now
        checklist.changed_by_id = actor.id
        checklist.changed_by_full_name = actor.full_name
        checklist.changes = append_changelog(
            checklist.changes, actor.full_name, "\n".join(line for line in lines if line)
        )

        saved = await self._checklists.save(checklist)
        await self._uow.commit()
        log.info("Checklist #%s updated by user #%s.", saved.id, actor.id)
        return ChecklistMapper.to_result(saved)

    @staticmethod
    def _snapshot(checklist: Checklist) -> dict[str, object]:
        return {
            "title": checklist.title,
            "definition_version": checklist.definition_version,
            "item_count": checklist.item_count,
            "project_id": checklist.project_id,
            "product_id": checklist.product_id,
            "verdict": checklist.verdict.value,
        }
