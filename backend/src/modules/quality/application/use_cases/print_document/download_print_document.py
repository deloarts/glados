"""
Renders a template straight to bytes for the caller to hand back as a file
download. No printer involved at all. Shares render_print_document with
PrintDocument, so a downloaded file and a printed one are byte-for-byte the
same rendering; the only difference is what happens to the bytes
afterwards. This is the generic answer to "docket printing should be
possible ... even just a pdf download". Nothing here is specific to
dockets either, a label classifier downloads its rendered ZPL text the
same way.

Unlike PrintDocument, a download is a single synchronous user action (like
a preview), not a fan-out or an auto-print occurrence that must degrade
gracefully, so this raises on failure rather than writing a failed job
row.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.print_render import RenderedDocument
from src.modules.quality.application.services.print_render import render_print_document
from src.modules.quality.application.services.print_roots import IPrintRootResolver
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.errors import DocketSpecInvalidError
from src.modules.quality.domain.errors import PrintRootNotFoundError
from src.modules.quality.domain.errors import PrintTemplateNotConfiguredError
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


class DownloadPrintDocument:
    def __init__(
        self,
        template_repo: IPrintTemplateRepository,
        job_repo: IPrintJobRepository,
        root_resolver: IPrintRootResolver,
        *,
        docket_renderer: IDocketRenderer,
        asset_resolver: DocketAssetResolver | None,
        domain_url: str,
        uow: IUnitOfWork,
    ) -> None:
        self._templates = template_repo
        self._jobs = job_repo
        self._resolver = root_resolver
        self._docket_renderer = docket_renderer
        self._asset_resolver = asset_resolver
        self._domain_url = domain_url
        self._uow = uow

    async def execute(
        self, actor: User, classifier: str, root_type: str, root_id: int
    ) -> RenderedDocument:
        PrinterRules.assert_can_print(actor)

        template = found_or_raise(
            await self._templates.get_by_classifier(classifier),
            PrintTemplateNotFoundError,
            f"No print template for classifier {classifier!r}.",
        )
        if not template.enabled or not template.source:
            raise PrintTemplateNotConfiguredError(
                f"Print template {classifier!r} is not configured or is disabled."
            )

        root = found_or_raise(
            await self._resolver.resolve(root_type, root_id),
            PrintRootNotFoundError,
            f"{root_type} #{root_id} not found.",
        )

        try:
            rendered = await render_print_document(
                template,
                root,
                root_type,
                domain_url=self._domain_url,
                actor_full_name=actor.full_name,
                docket_renderer=self._docket_renderer,
                asset_resolver=self._asset_resolver,
            )
        except ValueError as exc:
            raise DocketSpecInvalidError(f"Could not render {classifier!r}: {exc}") from exc

        job = PrintJob(
            id=0,
            created=now_utc(),
            template_id=template.id,
            printer_id=None,
            classifier=PrintClassifier(classifier),
            root_type=PrintRootType(root_type),
            root_id=root_id,
            copies=1,
            status=PrintJobStatus.SENT,
            error_message=None,
            rendered_zpl=rendered.rendered_zpl,
            document_bytes=len(rendered.payload),
            trigger=PrintJobTrigger.MANUAL,
            source_event_id=None,
            actor_id=actor.id,
        )
        saved_job = await self._jobs.save(job)
        await self._uow.commit()
        log.info(f"Downloaded {classifier!r}, job #{saved_job.id}.")

        return rendered
