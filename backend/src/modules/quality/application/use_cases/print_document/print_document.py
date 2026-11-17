"""
The print pipeline: resolve template -> resolve printer -> validate kind
match -> resolve root -> render -> commit the read transaction -> send ->
write and commit the job row -> return.

Deliberately never raises for a pipeline failure: it raises only for
InsufficientPermissionsError, which means the actor cannot even attempt
this print. Every other failure (missing template, missing, archived or
disabled printer, kind mismatch, missing root, unreachable printer) becomes
a status="failed" print_job row with as much of (template_id, printer_id)
filled in as was resolved before the failure, and is still returned as a
normal PrintJobResult rather than an exception.

This is what makes POST /print's per-item fan-out (see the print endpoint)
correct: one bad item does not need special-casing by its caller, and it
is the same contract a later auto-print handler needs, since a shop-floor
completion must succeed even when the printer is unplugged, with the
failure landing in print_job.status, never in the operator's face.

An auto-print arrives with `claimed_job`, the row its event delivery wrote
before calling (see handle_event_auto_print.py). The outcome is then stored
on that row instead of a new one. An unexpected exception (not a pipeline
failure) or a cancellation that happens before the printer was asked
deletes the claim again and propagates, so the event bus redelivers the
event and the print is tried once more. After the printer was asked the
claim stays, because the label may already be out and a second one must
not follow.
"""

from dataclasses import dataclass

from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.mappers.print_template_mapper import PrintJobMapper
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_classifiers import printer_kind_for
from src.modules.quality.application.services.print_render import render_print_document
from src.modules.quality.application.services.print_roots import IPrintRootResolver
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.errors import PrintRejectedError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.clock import now_utc


@dataclass
class _PrintAttempt:
    """Accumulates one execute() call's pipeline outputs as they resolve, so
    the job row written at the end reflects however far the pipeline got
    (see module docstring: a pipeline failure is never an exception)."""

    resolved_copies: int
    template_id: int | None = None
    resolved_printer_id: int | None = None
    rendered_zpl: str | None = None
    document_bytes: int | None = None
    error_message: str | None = None
    send_started: bool = False


class PrintDocument:
    def __init__(
        self,
        template_repo: IPrintTemplateRepository,
        printer_repo: IPrinterRepository,
        job_repo: IPrintJobRepository,
        root_resolver: IPrintRootResolver,
        *,
        gateway: IPrinterGateway,
        docket_renderer: IDocketRenderer,
        asset_resolver: DocketAssetResolver | None,
        domain_url: str,
        uow: IUnitOfWork,
    ) -> None:
        self._templates = template_repo
        self._printers = printer_repo
        self._jobs = job_repo
        self._resolver = root_resolver
        self._gateway = gateway
        self._docket_renderer = docket_renderer
        self._asset_resolver = asset_resolver
        self._domain_url = domain_url
        self._uow = uow

    async def _resolve_template(
        self, attempt: _PrintAttempt, classifier: str
    ) -> PrintTemplate | None:
        template = await self._templates.get_by_classifier(classifier)
        if not template:
            attempt.error_message = f"No print template for classifier {classifier!r}."
            return None
        attempt.template_id = template.id
        if not template.enabled or not template.source:
            attempt.error_message = (
                f"Print template {classifier!r} is not configured or is disabled."
            )
            return None
        return template

    async def _resolve_printer(
        self,
        attempt: _PrintAttempt,
        template: PrintTemplate,
        classifier: str,
        printer_id: int | None,
        copies: int | None,
    ) -> Printer | None:
        attempt.resolved_copies = copies if copies is not None else template.copies_fixed
        attempt.resolved_copies = max(1, min(attempt.resolved_copies, template.max_copies))

        effective_printer_id = printer_id if printer_id is not None else template.printer_id
        if effective_printer_id is None:
            attempt.error_message = f"No printer configured for classifier {classifier!r}."
            return None
        printer = await self._printers.get_by_id(effective_printer_id)
        if not printer:
            attempt.error_message = f"Printer #{effective_printer_id} not found."
            return None
        attempt.resolved_printer_id = printer.id
        out_of_use = PrinterRules.out_of_use_problem(printer)
        if out_of_use:
            attempt.error_message = out_of_use
            return None

        spec = CLASSIFIERS[PrintClassifier(classifier)]
        required_kind = printer_kind_for(spec.output_kind)
        if printer.kind != required_kind:
            attempt.error_message = (
                f"Classifier {classifier!r} needs a {required_kind!r} printer, "
                f"but printer #{printer.id} is {printer.kind.value!r}."
            )
            return None
        return printer

    async def _render_and_send(
        self,
        attempt: _PrintAttempt,
        actor: User,
        template: PrintTemplate,
        printer: Printer,
        classifier: str,
        root_type: str,
        root_id: int,
    ) -> None:
        root = await self._resolver.resolve(root_type, root_id)
        if root is None:
            attempt.error_message = f"{root_type} #{root_id} not found."
            return
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
            attempt.error_message = f"Could not render {classifier!r}: {exc}"
            return
        attempt.rendered_zpl = rendered.rendered_zpl
        attempt.document_bytes = len(rendered.payload)
        # Every caller only reads before printing, so nothing is pending here.
        # Ending the read transaction frees the connection while the printer,
        # which may be slow or offline, answers. The job row is written and
        # committed in a second transaction once the outcome is known.
        await self._uow.commit()
        attempt.send_started = True
        try:
            await self._gateway.send(
                printer, rendered.payload, rendered.content_type, attempt.resolved_copies
            )
        except (PrinterUnreachableError, PrintRejectedError) as exc:
            attempt.error_message = str(exc)

    async def _save_and_log(
        self,
        actor: User,
        classifier: str,
        root_type: str,
        root_id: int,
        trigger: str,
        source_event_id: str | None,
        attempt: _PrintAttempt,
        claimed_job: PrintJob | None,
    ) -> PrintJobResult:
        status = PrintJobStatus.FAILED if attempt.error_message else PrintJobStatus.SENT
        job = PrintJob(
            id=claimed_job.id if claimed_job else 0,
            created=claimed_job.created if claimed_job else now_utc(),
            template_id=attempt.template_id,
            printer_id=attempt.resolved_printer_id,
            classifier=PrintClassifier(classifier),
            root_type=PrintRootType(root_type),
            root_id=root_id,
            copies=attempt.resolved_copies,
            status=status,
            error_message=attempt.error_message,
            rendered_zpl=attempt.rendered_zpl,
            document_bytes=attempt.document_bytes,
            trigger=PrintJobTrigger(trigger),
            source_event_id=source_event_id,
            actor_id=actor.id,
        )
        if claimed_job is not None:
            saved_job = await self._jobs.finish_claimed(job)
        else:
            saved_job = await self._jobs.save(job)
        await self._uow.commit()

        if attempt.error_message:
            log.warning(f"Print of {classifier!r} failed: {attempt.error_message}")
        else:
            log.info(
                f"Printed {classifier!r} ({attempt.resolved_copies} copies), job #{saved_job.id}."
            )
        return PrintJobMapper.to_result(saved_job)

    async def execute(
        self,
        actor: User,
        classifier: str,
        root_type: str,
        root_id: int,
        *,
        printer_id: int | None = None,
        copies: int | None = None,
        trigger: str = "manual",
        source_event_id: str | None = None,
        claimed_job: PrintJob | None = None,
    ) -> PrintJobResult:
        # PRINT_DOCUMENTS gates *choosing* to print, so it applies to manual
        # prints only. An auto-print was authorised when an admin armed the
        # template (WRITE_PRINTERS); the operator who recorded the
        # delivery or completion did not ask for it and must not need print
        # rights for the shop-floor action to succeed. `actor` is still the
        # person who caused it, recorded on the job row for attribution.
        if trigger == PrintJobTrigger.MANUAL.value:
            PrinterRules.assert_can_print(actor)  # not allowed to attempt -> raise, no job row

        attempt = _PrintAttempt(resolved_copies=copies if copies is not None else 1)

        try:
            template = await self._resolve_template(attempt, classifier)
            printer = None
            if template is not None:
                printer = await self._resolve_printer(
                    attempt, template, classifier, printer_id, copies
                )
            if template is not None and printer is not None:
                await self._render_and_send(
                    attempt, actor, template, printer, classifier, root_type, root_id
                )

            return await self._save_and_log(
                actor,
                classifier,
                root_type,
                root_id,
                trigger,
                source_event_id,
                attempt,
                claimed_job,
            )
        except BaseException:
            # BaseException, so a worker shutdown that cancels the delivery
            # before the send frees the claim for the redelivery too.
            if claimed_job is not None and not attempt.send_started:
                await self._release_claim(claimed_job)
            raise

    async def _release_claim(self, claimed_job: PrintJob) -> None:
        """Deletes the claim of a print that was never sent, so the event's
        redelivery can print it. A failure here is logged and swallowed, so
        the original exception is the one that propagates; the claim then
        stays in status printing and the print is not retried."""
        try:
            await self._uow.rollback()
            await self._jobs.release_claim(claimed_job.id)
            await self._uow.commit()
        except Exception as exc:
            log.error(
                f"Could not release the claim of auto-print job #{claimed_job.id} "
                f"({claimed_job.classifier.value!r}): {exc}. The print stays unsent."
            )
