"""Converts between PrintTemplate/PrintJob domain entities and DTOs, enriching with
classifier specs."""

from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.dto.print_template_dto import PrintTemplateResult
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_classifiers import triggers_for
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier


class PrintTemplateMapper:
    @staticmethod
    def to_result(entity: PrintTemplate) -> PrintTemplateResult:
        classifier = PrintClassifier(entity.classifier)
        spec = CLASSIFIERS[classifier]
        return PrintTemplateResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            classifier=entity.classifier,
            output_kind=spec.output_kind.value,
            root_type=spec.root_type.value,
            trigger=entity.trigger,
            available_triggers=[t.value for t in triggers_for(classifier)],
            copies_rules=[r.value for r in spec.copies_rules],
            source=entity.source,
            field_map=entity.field_map,
            printer_id=entity.printer_id,
            printer_name=entity.printer_name,
            auto_print=entity.auto_print,
            copies_rule=entity.copies_rule,
            copies_fixed=entity.copies_fixed,
            max_copies=entity.max_copies,
            design_dpi=entity.design_dpi,
            label_width_mm=entity.label_width_mm,
            label_height_mm=entity.label_height_mm,
            paper=entity.paper,
            enabled=entity.enabled,
            note=entity.note,
            creator_id=entity.creator_id,
            creator_full_name=entity.creator_full_name,
            changed_by_id=entity.changed_by_id,
            changed_by_full_name=entity.changed_by.full_name if entity.changed_by else "",
            changes=entity.changes,
        )


class PrintJobMapper:
    @staticmethod
    def to_result(entity: PrintJob) -> PrintJobResult:
        return PrintJobResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            template_id=entity.template_id,
            printer_id=entity.printer_id,
            classifier=entity.classifier,
            root_type=entity.root_type,
            root_id=entity.root_id,
            copies=entity.copies,
            status=entity.status,
            error_message=entity.error_message,
            document_bytes=entity.document_bytes,
            trigger=entity.trigger,
            actor_id=entity.actor_id,
            actor_full_name=entity.actor_full_name,
        )
