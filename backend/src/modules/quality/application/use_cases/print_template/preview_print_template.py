"""
Resolve root -> build field values -> render. No printer, no job row;
this is the read-only "what would this look like" text path. ZPL only:
a docket has no textual rendering, its preview.png IS the preview (see
RenderPrintTemplateImage, which renders a docket directly rather than
going through this use case).
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.print_template_dto import PreviewPrintTemplateResult
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_roots import IPrintRootResolver
from src.modules.quality.application.services.print_value_resolver import resolve_field_values
from src.modules.quality.domain.errors import PrintRootNotFoundError
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.domain.services.zpl_template import render_zpl
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)


class PreviewPrintTemplate:
    def __init__(
        self,
        template_repo: IPrintTemplateRepository,
        root_resolver: IPrintRootResolver,
        *,
        domain_url: str,
    ) -> None:
        self._templates = template_repo
        self._resolver = root_resolver
        self._domain_url = domain_url

    async def execute(
        self, actor: User, classifier: str, root_type: str, root_id: int
    ) -> PreviewPrintTemplateResult:
        PrinterRules.assert_can_print(actor)

        template = found_or_raise(
            await self._templates.get_by_classifier(classifier),
            PrintTemplateNotFoundError,
            f"No print template for classifier {classifier!r}.",
        )

        if not template.source:
            return PreviewPrintTemplateResult(
                rendered_zpl=None, warnings=["template has no content yet"]
            )

        if CLASSIFIERS[PrintClassifier(classifier)].output_kind != PrintOutputKind.ZPL:
            return PreviewPrintTemplateResult(
                rendered_zpl=None,
                warnings=["this classifier has no textual preview, see preview.png"],
            )

        root = found_or_raise(
            await self._resolver.resolve(root_type, root_id),
            PrintRootNotFoundError,
            f"{root_type} #{root_id} not found.",
        )

        values = await resolve_field_values(
            template.field_map, root, domain_url=self._domain_url, actor_full_name=actor.full_name
        )
        rendered = render_zpl(template.source, values)

        return PreviewPrintTemplateResult(rendered_zpl=rendered, warnings=[])
