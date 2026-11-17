"""Use cases for retrieving print templates, sorted by classifier registry order."""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.quality.application.dto.print_template_dto import PrintTemplateResult
from src.modules.quality.application.mappers.print_template_mapper import PrintTemplateMapper
from src.modules.quality.application.services.print_classifiers import display_order_of
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)


class GetPrintTemplate:
    def __init__(self, template_repo: IPrintTemplateRepository) -> None:
        self._templates = template_repo

    async def execute(self, classifier: str) -> PrintTemplateResult:
        template = found_or_raise(
            await self._templates.get_by_classifier(classifier),
            PrintTemplateNotFoundError,
            f"No print template for classifier {classifier!r}.",
        )
        return PrintTemplateMapper.to_result(template)


class GetPrintTemplates:
    def __init__(self, template_repo: IPrintTemplateRepository) -> None:
        self._templates = template_repo

    async def execute(self) -> list[PrintTemplateResult]:
        # Sorted by the classifier registry's own order, not the repo's row
        # id: the settings tables render this list as is, and the insertion
        # order of the slots says nothing about where a classifier belongs.
        return sorted(
            (PrintTemplateMapper.to_result(t) for t in await self._templates.get_all()),
            key=lambda result: display_order_of(result.classifier),
        )
