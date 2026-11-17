"""
The settings-surface write path: fetch by classifier, validate against the
classifier's fixed shape (trigger root-type match, copies rule, ZPL
placeholder/field-map coverage, printer kind), then save. There is no create or delete:
rows are seeded, never made or removed here.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.print_template_dto import PrintTemplateResult
from src.modules.quality.application.dto.print_template_dto import UpdatePrintTemplateCommand
from src.modules.quality.application.mappers.print_template_mapper import PrintTemplateMapper
from src.modules.quality.application.services.docket_spec import validate_docket_spec
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_classifiers import ClassifierSpec
from src.modules.quality.application.services.print_classifiers import printer_kind_for
from src.modules.quality.application.services.print_classifiers import triggers_for
from src.modules.quality.application.services.print_field_sources import valid_source_names
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.errors import DocketSpecInvalidError
from src.modules.quality.domain.errors import PrintCopiesRuleInvalidError
from src.modules.quality.domain.errors import PrinterKindMismatchError
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.errors import PrintFieldMapInvalidError
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.domain.errors import PrintTriggerInvalidError
from src.modules.quality.domain.errors import ZplTemplateInvalidError
from src.modules.quality.domain.services.print_template_rules import PrintTemplateRules
from src.modules.quality.domain.services.zpl_template import validate_zpl_template
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc

_TRACKED_FIELDS = (
    "trigger",
    "source",
    "field_map",
    "printer_id",
    "auto_print",
    "copies_rule",
    "copies_fixed",
    "max_copies",
    "design_dpi",
    "label_width_mm",
    "label_height_mm",
    "paper",
    "enabled",
    "note",
)

# The command carries these as plain strings; the entity holds the enums.
_ENUM_FIELDS: dict[str, type[PrintTrigger] | type[PrintCopiesRule]] = {
    "trigger": PrintTrigger,
    "copies_rule": PrintCopiesRule,
}


class UpdatePrintTemplate:
    def __init__(
        self,
        template_repo: IPrintTemplateRepository,
        printer_repo: IPrinterRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._templates = template_repo
        self._printers = printer_repo
        self._uow = uow

    def _resolve_effective_trigger(
        self,
        cmd: UpdatePrintTemplateCommand,
        template: PrintTemplate,
        classifier: str,
        classifier_enum: PrintClassifier,
    ) -> str | None:
        # "provided" (in cmd.model_fields_set), not `is not None`: trigger,
        # printer_id, paper and note are all legitimately nullable: a
        # None here can mean "clear it" (e.g. the editor's trigger select
        # set to "manual only"), not just "wasn't sent". Requires the
        # endpoint to build cmd via model_dump(exclude_unset=True), not a
        # plain model_dump(), the same pattern as update_lot.py's
        # required_delivery_date.
        effective_trigger = cmd.trigger if "trigger" in cmd.model_fields_set else template.trigger
        if effective_trigger is None:
            return None
        allowed = triggers_for(classifier_enum)
        if PrintTrigger(effective_trigger) not in allowed:
            raise PrintTriggerInvalidError(
                f"Trigger {effective_trigger!r} is not valid for classifier "
                f"{classifier!r}; allowed: {', '.join(t.value for t in allowed)}."
            )
        return effective_trigger

    def _resolve_effective_copies_rule(
        self,
        cmd: UpdatePrintTemplateCommand,
        template: PrintTemplate,
        spec: ClassifierSpec,
        classifier: str,
    ) -> str:
        # copies_rule/field_map are non-nullable on the domain entity (no
        # "clear it" state exists), so a stray explicit null is treated
        # the same as "not provided" rather than propagating None into
        # effective_*, unlike trigger/printer_id/paper/note above.
        effective_copies_rule = (
            cmd.copies_rule
            if "copies_rule" in cmd.model_fields_set and cmd.copies_rule is not None
            else template.copies_rule
        )
        if effective_copies_rule not in (r.value for r in spec.copies_rules):
            raise PrintCopiesRuleInvalidError(
                f"Copies rule {effective_copies_rule!r} is not valid for classifier {classifier!r}."
            )
        return effective_copies_rule

    def _resolve_effective_field_map(
        self,
        cmd: UpdatePrintTemplateCommand,
        template: PrintTemplate,
        classifier_enum: PrintClassifier,
        effective_trigger: str | None,
    ) -> dict[str, str]:
        effective_field_map = (
            cmd.field_map
            if "field_map" in cmd.model_fields_set and cmd.field_map is not None
            else template.field_map
        )
        trigger_enum = PrintTrigger(effective_trigger) if effective_trigger else None
        allowed_sources = valid_source_names(classifier_enum, trigger_enum)
        unknown_sources = set(effective_field_map.values()) - allowed_sources
        if unknown_sources:
            raise PrintFieldMapInvalidError(
                f"field_map references unknown source(s): {', '.join(sorted(unknown_sources))}."
            )
        return effective_field_map

    def _validate_source(
        self,
        cmd: UpdatePrintTemplateCommand,
        template: PrintTemplate,
        spec: ClassifierSpec,
        effective_field_map: dict[str, str],
    ) -> None:
        effective_source = cmd.source if "source" in cmd.model_fields_set else template.source
        if not effective_source:
            return
        if spec.output_kind == PrintOutputKind.ZPL:
            try:
                validate_zpl_template(effective_source, effective_field_map)
            except ValueError as exc:
                raise ZplTemplateInvalidError(str(exc)) from exc
        elif spec.output_kind == PrintOutputKind.PDF_DOCKET:
            try:
                validate_docket_spec(effective_source, effective_field_map)
            except ValueError as exc:
                raise DocketSpecInvalidError(str(exc)) from exc

    async def _validate_printer(
        self, cmd: UpdatePrintTemplateCommand, spec: ClassifierSpec, classifier: str
    ) -> None:
        if cmd.printer_id is None:
            return
        printer = found_or_raise(
            await self._printers.get_by_id(cmd.printer_id),
            PrinterNotFoundError,
            f"Printer #{cmd.printer_id} not found.",
        )
        required_kind = printer_kind_for(spec.output_kind)
        if printer.kind != required_kind:
            raise PrinterKindMismatchError(
                f"Classifier {classifier!r} needs a {required_kind!r} printer, "
                f"but printer #{printer.id} is {printer.kind.value!r}."
            )

    def _apply_changes(
        self, template: PrintTemplate, cmd: UpdatePrintTemplateCommand
    ) -> str | None:
        old = {field: getattr(template, field) for field in _TRACKED_FIELDS}
        for field in _TRACKED_FIELDS:
            if field in cmd.model_fields_set:
                value = getattr(cmd, field)
                if value is not None and field in _ENUM_FIELDS:
                    value = _ENUM_FIELDS[field](value)
                setattr(template, field, value)
        new = {field: getattr(template, field) for field in _TRACKED_FIELDS}
        return diff_changes(old, new)

    async def execute(
        self, actor: User, classifier: str, cmd: UpdatePrintTemplateCommand
    ) -> PrintTemplateResult:
        template = found_or_raise(
            await self._templates.get_by_classifier(classifier),
            PrintTemplateNotFoundError,
            f"No print template for classifier {classifier!r}.",
        )

        PrintTemplateRules.assert_can_update(actor)

        classifier_enum = PrintClassifier(classifier)
        spec = CLASSIFIERS[classifier_enum]

        effective_trigger = self._resolve_effective_trigger(
            cmd, template, classifier, classifier_enum
        )
        self._resolve_effective_copies_rule(cmd, template, spec, classifier)
        effective_field_map = self._resolve_effective_field_map(
            cmd, template, classifier_enum, effective_trigger
        )
        self._validate_source(cmd, template, spec, effective_field_map)
        await self._validate_printer(cmd, spec, classifier)

        changelog_entry = self._apply_changes(template, cmd)

        template.changed = now_utc()
        template.changes = append_changelog(
            template.changes, actor.full_name, changelog_entry or "Print template updated."
        )
        if template.creator_id is None:
            template.creator_id = actor.id

        saved = await self._templates.save(template)
        await self._uow.commit()

        log.info(f"Updated print template {classifier!r}.")

        return PrintTemplateMapper.to_result(saved)
