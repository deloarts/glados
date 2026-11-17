"""
Creates and updates flow sequences. A sequence always belongs to one live
product and starts at the revision the admin settings name as the first
one, with the next document number of the sequence numbering format. Its
content is checked against the product's devices, their positions and the
product's variants (see sequence_rules.check_content). An update is saved
only by the holder of the edit lock, who is then remembered as one of its
editors; the product never changes.
"""

from dataclasses import replace

from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.sequence_dto import CreateSequenceCommand
from src.modules.quality.application.dto.sequence_dto import SequenceResult
from src.modules.quality.application.dto.sequence_dto import UpdateSequenceCommand
from src.modules.quality.application.mappers.sequence_mapper import SequenceMapper
from src.modules.quality.application.services import controlled_documents
from src.modules.quality.application.use_cases.sequence._context import SequenceContextLoader
from src.modules.quality.domain.entities.sequence import Sequence
from src.modules.quality.domain.errors import SequenceNotFoundError
from src.modules.quality.domain.services import document_control
from src.modules.quality.domain.services.sequence_rules import SequenceRules
from src.modules.quality.domain.services.sequence_rules import check_content
from src.modules.quality.domain.services.sequence_rules import clean_name
from src.modules.quality.domain.services.sequence_rules import references_of
from src.modules.quality.domain.value_objects.sequence_content import steps_from_data
from src.modules.quality.ports.outbound.repositories.sequence_repository import ISequenceRepository
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceKindQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductVariantQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc


def _assert_product_only(project_id: int | None, product_id: int | None) -> None:
    """A sequence has no project; the product is always given."""


class CreateSequence:
    def __init__(
        self,
        sequence_repo: ISequenceRepository,
        project_repo: IProjectQueries,
        product_repo: IProductQueries,
        admin_settings_repo: IFulfillmentSettingsRepository,
        device_repo: IProductDeviceQueries,
        kind_repo: IProductDeviceKindQueries,
        variant_repo: IProductVariantQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._sequences = sequence_repo
        self._projects = project_repo
        self._products = product_repo
        self._admin_settings = admin_settings_repo
        self._context = SequenceContextLoader(device_repo, kind_repo, variant_repo)
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateSequenceCommand) -> SequenceResult:
        SequenceRules.assert_can_create(actor)
        await controlled_documents.assert_owner_exists(
            self._projects,
            self._products,
            None,
            cmd.product_id,
            valid_owner=_assert_product_only,
            plural="sequences",
        )
        name = clean_name(cmd.name)
        steps = steps_from_data(cmd.steps)
        check_content(steps, await self._context.load(cmd.product_id))
        settings = await self._admin_settings.get_made_items()

        now = now_utc()
        sequence = Sequence(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Sequence created."),
            creator_id=actor.id,
            revision=settings.revision_start,
            product_id=cmd.product_id,
            name=name,
            steps=steps,
        )

        async def write() -> Sequence:
            number = await self._sequences.next_document_number(settings.sequence_number_format)
            return await self._sequences.save(replace(sequence, document_number=number))

        saved = await commit_with_number_retry(self._uow, write)
        log.info(
            "Sequence #%s of product #%s created by user #%s.", saved.id, saved.product_id, actor.id
        )
        return SequenceMapper.to_result(saved)


class UpdateSequence:
    def __init__(
        self,
        sequence_repo: ISequenceRepository,
        device_repo: IProductDeviceQueries,
        kind_repo: IProductDeviceKindQueries,
        variant_repo: IProductVariantQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._sequences = sequence_repo
        self._context = SequenceContextLoader(device_repo, kind_repo, variant_repo)
        self._uow = uow

    async def execute(
        self, actor: User, sequence_id: int, cmd: UpdateSequenceCommand
    ) -> SequenceResult:
        SequenceRules.assert_can_write(actor, "update")
        sequence = found_or_raise(
            await self._sequences.get_for_update(sequence_id),
            SequenceNotFoundError,
            f"Sequence #{sequence_id} not found.",
        )
        SequenceRules.assert_can_update(actor, sequence)
        now = now_utc()
        document_control.assert_holds_lock(sequence, actor, now, f"Sequence #{sequence.id}")
        document_control.renew_lock(sequence, actor, now)
        document_control.record_editor(sequence, actor)

        name = clean_name(cmd.name)
        steps = steps_from_data(cmd.steps)
        context = await self._context.load(sequence.product_id, references_of(sequence.steps))
        check_content(steps, context)

        lines: list[str] = []
        if name != sequence.name:
            lines.append(diff_changes({"name": sequence.name}, {"name": name}, "Sequence updated:"))
        if steps != sequence.steps:
            lines.append("Steps changed.")
        sequence.name = name
        sequence.steps = steps
        sequence.changed = now
        sequence.changed_by_id = actor.id
        sequence.changed_by_full_name = actor.full_name
        sequence.changes = append_changelog(
            sequence.changes, actor.full_name, "\n".join(lines) or "No changes."
        )

        saved = await self._sequences.save(sequence)
        await self._uow.commit()
        log.info("Sequence #%s updated by user #%s.", saved.id, actor.id)
        return SequenceMapper.to_result(saved)
