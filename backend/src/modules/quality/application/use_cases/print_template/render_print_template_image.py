"""
Renders a template to a PNG preview: the ZPL rasterizer for labels, the
docket renderer's own render_preview_png for dockets, both returning the
same (bytes, warnings) shape so one preview.png endpoint serves both kinds.
"""

from functools import partial

from anyio import to_thread

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.docket_pagination import paginate
from src.modules.quality.application.services.docket_spec import parse_docket_spec
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_render import build_rows
from src.modules.quality.application.services.print_roots import IPrintRootResolver
from src.modules.quality.application.services.print_value_resolver import resolve_field_values
from src.modules.quality.application.services.print_value_resolver import resolve_image_sources
from src.modules.quality.application.use_cases.print_template.preview_print_template import (
    PreviewPrintTemplate,
)
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.errors import PrintRootNotFoundError
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.modules.quality.ports.outbound.zpl_rasterizer_port import IZplRasterizer


class RenderPrintTemplateImage:
    def __init__(
        self,
        template_repo: IPrintTemplateRepository,
        printer_repo: IPrinterRepository,
        root_resolver: IPrintRootResolver,
        preview: PreviewPrintTemplate,
        *,
        rasterizer: IZplRasterizer,
        docket_renderer: IDocketRenderer,
        asset_resolver: DocketAssetResolver | None,
        domain_url: str,
    ) -> None:
        self._templates = template_repo
        self._printers = printer_repo
        self._resolver = root_resolver
        self._preview = preview
        self._rasterizer = rasterizer
        self._docket_renderer = docket_renderer
        self._asset_resolver = asset_resolver
        self._domain_url = domain_url

    async def execute(
        self, actor: User, classifier: str, root_type: str, root_id: int
    ) -> tuple[bytes, list[str]]:
        PrinterRules.assert_can_print(actor)

        template = found_or_raise(
            await self._templates.get_by_classifier(classifier),
            PrintTemplateNotFoundError,
            f"No print template for classifier {classifier!r}.",
        )

        if not template.source:
            return b"", ["template has no content yet"]

        spec = CLASSIFIERS[PrintClassifier(classifier)]
        if spec.output_kind != PrintOutputKind.PDF_DOCKET:
            return await self._render_zpl_preview(actor, template, classifier, root_type, root_id)

        root = found_or_raise(
            await self._resolver.resolve(root_type, root_id),
            PrintRootNotFoundError,
            f"{root_type} #{root_id} not found.",
        )

        try:
            docket_spec = parse_docket_spec(template.source)
        except ValueError as exc:
            return b"", [str(exc)]

        rows = await build_rows(docket_spec, template.field_map, root, spec, self._asset_resolver)
        values = await resolve_field_values(
            template.field_map,
            root,
            domain_url=self._domain_url,
            actor_full_name=actor.full_name,
            asset_resolver=self._asset_resolver,
            row_count=len(rows) if spec.has_rows else None,
        )
        images = await resolve_image_sources(
            template.field_map,
            root,
            root_type,
            domain_url=self._domain_url,
            asset_resolver=self._asset_resolver,
            qr_renderer=self._docket_renderer,
        )
        return await to_thread.run_sync(
            self._docket_renderer.render_preview_png,
            paginate(docket_spec, values, images, rows),
        )

    async def _render_zpl_preview(
        self, actor: User, template: PrintTemplate, classifier: str, root_type: str, root_id: int
    ) -> tuple[bytes, list[str]]:
        preview = await self._preview.execute(actor, classifier, root_type, root_id)
        if not preview.rendered_zpl:
            return b"", preview.warnings

        # Match the assigned printer's FORMAT CONVERT factor when one is
        # set, so the preview reflects what THAT printer will actually do
        # rather than assuming 1:1, the exact bug class that made the
        # first two prototype labels overshoot the stock.
        format_convert_factor = 1
        if template.printer_id is not None:
            printer = await self._printers.get_by_id(template.printer_id)
            if printer and printer.format_convert_factor:
                format_convert_factor = printer.format_convert_factor

        png, warnings = await to_thread.run_sync(
            partial(
                self._rasterizer.rasterize,
                preview.rendered_zpl,
                design_dpi=template.design_dpi or 300,
                format_convert_factor=format_convert_factor,
            )
        )
        return png, [*preview.warnings, *warnings]
