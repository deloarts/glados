"""
Clears a template's own content back to an unconfigured slot. Glados ships
no built-in content to restore: a classifier's row starts out as an empty
slot, and recommended content is imported from the repository's templates
folder. This is a clear action, not a restore.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.print_template_dto import PrintTemplateResult
from src.modules.quality.application.mappers.print_template_mapper import PrintTemplateMapper
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.domain.services.print_template_rules import PrintTemplateRules
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ResetPrintTemplate:
    def __init__(self, template_repo: IPrintTemplateRepository, *, uow: IUnitOfWork) -> None:
        self._templates = template_repo
        self._uow = uow

    async def execute(self, actor: User, classifier: str) -> PrintTemplateResult:
        template = found_or_raise(
            await self._templates.get_by_classifier(classifier),
            PrintTemplateNotFoundError,
            f"No print template for classifier {classifier!r}.",
        )

        PrintTemplateRules.assert_can_update(actor)

        template.source = None
        template.field_map = {}
        template.enabled = False
        template.design_dpi = None
        template.label_width_mm = None
        template.label_height_mm = None
        template.paper = None
        # Trigger/printer/auto_print/copies_rule are left alone: clearing
        # content should not silently switch off an admin's auto-print
        # wiring or unassign the printer they chose.

        template.changed = now_utc()
        template.changes = append_changelog(
            template.changes, actor.full_name, "Print template content cleared."
        )

        saved = await self._templates.save(template)
        await self._uow.commit()

        log.info(f"Cleared print template {classifier!r}.")

        return PrintTemplateMapper.to_result(saved)
