"""
Turns domain events into prints. Invoked by the event bus worker for every
message in the "auto_print" consumer group, the same shape as
HandleEventNotifications, and for the same reason: a printer that is
offline, paused or out of media must never fail or slow the shop-floor
action that triggered it. The event bus is that isolation boundary.

There is no per-classifier or per-trigger code here. The handler walks the
TRIGGERS registry, matches the event by type, and asks each matching spec
for the root id, the actor and any per-occurrence quantity; which
templates are armed for that moment is a DB query. Adding a printable
moment is a TRIGGERS entry, not a branch in this file.

Idempotency: Redis Streams redeliver a message when a worker crashes after
acting but before acknowledging, the reclaim scan hands a slow delivery to
a second worker after 60 seconds, and `admin republish-outbox` puts handled
events back on the stream. A repeated notification is merely annoying; a
repeated print emits duplicate *physical* labels. So each template's job
row is claimed before anything is sent: an insert in status printing under
the unique (classifier, source_event_id) index that does nothing on a
conflict, committed at once. Only the delivery whose insert wrote the row
prints, and PrintDocument then stores the outcome on that row. Of two
deliveries at once the later insert waits for the earlier transaction and
then writes nothing, the same cure as handle_event_notifications.py, with
higher stakes.

A claim whose print was never sent is deleted again when the delivery
fails, so the event bus's redelivery prints it (see PrintDocument). A
delivery that stops for good after the send, or whose process dies between
the claim and the outcome, leaves the row in status printing, and the
event is not printed again automatically: one missing label is the safer
failure than a second one.
"""

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.services.print_classifiers import TRIGGERS
from src.modules.quality.application.services.print_copies import resolve_auto_print_copies
from src.modules.quality.application.services.print_roots import IPrintRootResolver
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.ports.outbound.repositories.print_job_repository import IPrintJobRepository
from src.modules.quality.ports.outbound.repositories.print_template_repository import (
    IPrintTemplateRepository,
)
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc


class HandleEventAutoPrint:
    def __init__(
        self,
        template_repo: IPrintTemplateRepository,
        job_repo: IPrintJobRepository,
        user_repo: IUserRepository,
        root_resolver: IPrintRootResolver,
        print_document: PrintDocument,
        uow: IUnitOfWork,
    ) -> None:
        self._templates = template_repo
        self._jobs = job_repo
        self._users = user_repo
        self._resolver = root_resolver
        self._print = print_document
        self._uow = uow

    async def execute(self, event: DomainEvent, source_event_id: str) -> None:
        for trigger, spec in TRIGGERS.items():
            if not isinstance(event, spec.event):
                continue

            # None = this moment does not apply to this particular event
            # (a BOUGHT delivery reaching the SOURCE trigger, a lot
            # completing with no made item denormalized on the event).
            root_id = spec.root_id_from(event)
            if root_id is None:
                continue

            templates = await self._templates.get_armed_by_trigger(trigger.value)
            if not templates:
                continue

            actor = await self._users.get_by_id(spec.actor_id_from(event))
            if actor is None:
                log.warning(
                    f"Auto-print skipped for trigger {trigger.value!r}: actor "
                    f"#{spec.actor_id_from(event)} not found."
                )
                continue

            for template in templates:
                # Only per_lot_quantity needs the record itself; resolving
                # it for the other rules would be a query for nothing.
                root = (
                    await self._resolver.resolve(spec.root_type.value, root_id)
                    if template.copies_rule == PrintCopiesRule.PER_LOT_QUANTITY.value
                    else None
                )
                copies = resolve_auto_print_copies(template, spec, event, root)

                claim = await self._jobs.claim_for_event(
                    PrintJob(
                        id=0,
                        created=now_utc(),
                        template_id=template.id,
                        printer_id=template.printer_id,
                        classifier=template.classifier,
                        root_type=spec.root_type,
                        root_id=root_id,
                        copies=copies,
                        status=PrintJobStatus.PRINTING,
                        error_message=None,
                        rendered_zpl=None,
                        document_bytes=None,
                        trigger=PrintJobTrigger.AUTO,
                        source_event_id=source_event_id,
                        actor_id=actor.id,
                    )
                )
                # Committed before anything is sent, so a concurrent delivery
                # waiting on the same key sees the claim and backs off.
                await self._uow.commit()
                if claim is None:
                    continue  # another delivery of this event owns this print

                await self._print.execute(
                    actor,
                    template.classifier,
                    spec.root_type.value,
                    root_id,
                    copies=copies,
                    trigger=PrintJobTrigger.AUTO.value,
                    source_event_id=source_event_id,
                    claimed_job=claim,
                )
