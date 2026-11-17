"""Use case for restoring an archived printer and publishing the PrinterRestored event.

No uniqueness pre-check: printer has no partial unique index scoped to
`archived`, so restoring one can never violate a live-row constraint."""

from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.application.mappers.printer_mapper import PrinterMapper
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.events.printer_events import PrinterRestored
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class RestorePrinter:
    def __init__(
        self,
        printer_repo: IPrinterRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._printers = printer_repo
        self._bus = event_bus
        self._uow = uow

    async def execute(self, actor: User, printer_id: int) -> PrinterResult:
        PrinterRules.assert_can_restore(actor)

        async def _before_save(printer: Printer) -> None:
            printer.changed = now_utc()
            printer.changes = append_changelog(
                printer.changes, actor.full_name, "Printer restored."
            )

        saved = await set_archived(
            entity_id=printer_id,
            archived=False,
            load=self._printers.get_by_id,
            not_found=lambda pid: PrinterNotFoundError(f"Printer #{pid} not found."),
            save=self._printers.save,
            before_save=_before_save,
        )

        await self._bus.publish(
            PrinterRestored(printer_id=saved.id, name=saved.name, actor_id=actor.id)
        )
        await self._uow.commit()

        log.info(f"Restored printer {saved.name!r}, ID={saved.id}.")

        return PrinterMapper.to_result(saved)
