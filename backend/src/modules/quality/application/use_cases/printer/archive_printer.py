"""Use case for archiving a printer and publishing the PrinterArchived event."""

from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.application.mappers.printer_mapper import PrinterMapper
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.events.printer_events import PrinterArchived
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ArchivePrinter:
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
        PrinterRules.assert_can_archive(actor)

        async def _before_save(printer: Printer) -> None:
            printer.changed = now_utc()
            printer.changes = append_changelog(
                printer.changes, actor.full_name, "Printer archived."
            )

        saved = await set_archived(
            entity_id=printer_id,
            archived=True,
            load=self._printers.get_by_id,
            not_found=lambda pid: PrinterNotFoundError(f"Printer #{pid} not found."),
            save=self._printers.save,
            before_save=_before_save,
        )

        await self._bus.publish(
            PrinterArchived(printer_id=saved.id, name=saved.name, actor_id=actor.id)
        )
        await self._uow.commit()

        log.info(f"Archived printer {saved.name!r}, ID={saved.id}.")

        return PrinterMapper.to_result(saved)
