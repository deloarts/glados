"""Update made-item catalogue settings: numbering formats, revision policy, and PDM
part-number pattern, with cross-validation against internal formats."""

from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    AdminMadeItemSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    UpdateMadeItemSettingsCommand,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.made_items import (
    MadeItemSettingsMapper,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.policies.item_field_ownership import REVISION_POLICY_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import RevisionFieldPolicy
from src.modules.catalogue.domain.policies.revision_scheme import START_REVISIONS
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.numbering_format import (
    assert_pattern_does_not_shadow_internal_formats,
)
from src.modules.platform.domain.services.numbering_format import validate_external_pattern
from src.modules.platform.domain.services.numbering_format import validate_numbering_format
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import today_in

_STATUS_VALUES = {s.value for s in MadeItemCatalogueStatus}


def _validate_revision_field_policy(policy: list[RevisionFieldPolicy]) -> None:
    """The stored policy must cover every REVISION_POLICY_FIELDS entry
    exactly once: no unknown field, none missing, none duplicated."""
    fields = [p.field for p in policy]
    if set(fields) != set(REVISION_POLICY_FIELDS) or len(fields) != len(REVISION_POLICY_FIELDS):
        raise ValueError(
            "revision_field_policy must contain exactly the fields "
            f"{list(REVISION_POLICY_FIELDS)} once each, got {fields!r}."
        )


class UpdateMadeItemSettings:
    def __init__(self, repo: ICatalogueSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateMadeItemSettingsCommand
    ) -> AdminMadeItemSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_made_items()
        today = today_in(await tenant_zone(self._repo))
        item_number_format = (
            cmd.item_number_format
            if cmd.item_number_format is not None
            else current.item_number_format
        )
        lot_number_format = (
            cmd.lot_number_format
            if cmd.lot_number_format is not None
            else current.lot_number_format
        )
        calculation_number_format = (
            cmd.calculation_number_format
            if cmd.calculation_number_format is not None
            else current.calculation_number_format
        )
        checklist_number_format = (
            cmd.checklist_number_format
            if cmd.checklist_number_format is not None
            else current.checklist_number_format
        )
        sequence_number_format = (
            cmd.sequence_number_format
            if cmd.sequence_number_format is not None
            else current.sequence_number_format
        )
        meeting_number_format = (
            cmd.meeting_number_format
            if cmd.meeting_number_format is not None
            else current.meeting_number_format
        )
        for template in (
            item_number_format,
            lot_number_format,
            calculation_number_format,
            checklist_number_format,
            sequence_number_format,
            meeting_number_format,
        ):
            validate_numbering_format(template)

        revision_start = (
            cmd.revision_start if cmd.revision_start is not None else current.revision_start
        )
        if revision_start not in START_REVISIONS:
            raise ValueError(
                f"Invalid revision start {revision_start!r}, must be one of {START_REVISIONS}."
            )

        revision_predecessor_status_web = (
            cmd.revision_predecessor_status_web
            if cmd.revision_predecessor_status_web is not None
            else current.revision_predecessor_status_web
        )
        if revision_predecessor_status_web not in ({"ask"} | _STATUS_VALUES):
            raise ValueError(
                "Invalid revision_predecessor_status_web "
                f"{revision_predecessor_status_web!r}, must be 'ask' or one of "
                f"{sorted(_STATUS_VALUES)}."
            )

        revision_predecessor_status_pdm = (
            cmd.revision_predecessor_status_pdm
            if cmd.revision_predecessor_status_pdm is not None
            else current.revision_predecessor_status_pdm
        )
        if revision_predecessor_status_pdm not in _STATUS_VALUES:
            raise ValueError(
                "Invalid revision_predecessor_status_pdm "
                f"{revision_predecessor_status_pdm!r}, must be one of {sorted(_STATUS_VALUES)}."
            )

        if cmd.revision_field_policy is not None:
            revision_field_policy = [
                RevisionFieldPolicy(
                    field=p.field,
                    web_requires_revision=p.web_requires_revision,
                    pdm_update_in_place=p.pdm_update_in_place,
                )
                for p in cmd.revision_field_policy
            ]
        else:
            revision_field_policy = current.revision_field_policy
        _validate_revision_field_policy(revision_field_policy)

        pdm_part_number_pattern = (
            cmd.pdm_part_number_pattern
            if cmd.pdm_part_number_pattern is not None
            else current.pdm_part_number_pattern
        )
        validate_external_pattern(pdm_part_number_pattern)
        # Only the made-item part-number format is checked here: lot
        # numbers are not part numbers and never collide with PDM ingest.
        assert_pattern_does_not_shadow_internal_formats(
            pdm_part_number_pattern, [item_number_format], today=today
        )

        settings = AdminMadeItemSettings(
            id=1,
            item_number_format=item_number_format,
            lot_number_format=lot_number_format,
            calculation_number_format=calculation_number_format,
            checklist_number_format=checklist_number_format,
            sequence_number_format=sequence_number_format,
            meeting_number_format=meeting_number_format,
            part_number_auto=(
                cmd.part_number_auto
                if cmd.part_number_auto is not None
                else current.part_number_auto
            ),
            part_number_editable=(
                cmd.part_number_editable
                if cmd.part_number_editable is not None
                else current.part_number_editable
            ),
            revision_start=revision_start,
            revision_separator=(
                cmd.revision_separator
                if cmd.revision_separator is not None
                else current.revision_separator
            ),
            revision_skip_ambiguous_letters=(
                cmd.revision_skip_ambiguous_letters
                if cmd.revision_skip_ambiguous_letters is not None
                else current.revision_skip_ambiguous_letters
            ),
            revision_only_newest_editable=(
                cmd.revision_only_newest_editable
                if cmd.revision_only_newest_editable is not None
                else current.revision_only_newest_editable
            ),
            revision_predecessor_status_web=revision_predecessor_status_web,
            revision_predecessor_status_pdm=revision_predecessor_status_pdm,
            revision_field_policy=revision_field_policy,
            web_creation_allowed=(
                cmd.web_creation_allowed
                if cmd.web_creation_allowed is not None
                else current.web_creation_allowed
            ),
            pdm_part_number_pattern=pdm_part_number_pattern,
        )
        saved = await self._repo.save_made_items(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="made_items",
                summary=f"Made item settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated made item settings.")
        return MadeItemSettingsMapper.made_items_to_result(saved, today=today)
