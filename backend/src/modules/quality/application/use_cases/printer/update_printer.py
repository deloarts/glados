"""Use case for updating printer configuration and tracking changes."""

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.application.dto.printer_dto import UpdatePrinterCommand
from src.modules.quality.application.mappers.printer_mapper import PrinterMapper
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.events.printer_events import PrinterUpdated
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.clock import now_utc

_TRACKED_FIELDS = (
    "name",
    "internal_name",
    "kind",
    "host",
    "port",
    "timeout_seconds",
    "transport",
    "ipp_uri_path",
    "head_dpi",
    "format_convert_factor",
    "default_media",
    "location",
    "vendor",
    "model",
    "firmware",
    "bought_item_ids",
    "enabled",
    "is_default",
    "note",
)


class UpdatePrinter:
    def __init__(
        self,
        printer_repo: IPrinterRepository,
        bought_item_repo: IBoughtItemQueries,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        self._printers = printer_repo
        self._bought_items = bought_item_repo
        self._bus = event_bus
        self._uow = uow

    async def execute(
        self, actor: User, printer_id: int, cmd: UpdatePrinterCommand
    ) -> PrinterResult:
        PrinterRules.assert_can_update(actor)
        if cmd.host is not None:
            PrinterRules.assert_host_allowed(cmd.host)

        printer = found_or_raise(
            await self._printers.get_by_id(printer_id),
            PrinterNotFoundError,
            f"Printer #{printer_id} not found.",
        )

        if cmd.bought_item_ids is not None:
            for bought_item_id in cmd.bought_item_ids:
                if not await self._bought_items.get_by_id(bought_item_id):
                    raise BoughtItemNotFoundError(f"Bought item #{bought_item_id} not found.")

        old = {field: getattr(printer, field) for field in _TRACKED_FIELDS}

        for field in _TRACKED_FIELDS:
            value = getattr(cmd, field)
            if value is not None:
                setattr(printer, field, value)

        new = {field: getattr(printer, field) for field in _TRACKED_FIELDS}
        changelog_entry = diff_changes(old, new)

        printer.changed = now_utc()
        printer.changes = append_changelog(printer.changes, actor.full_name, changelog_entry)

        saved = await self._printers.save(printer)
        if saved.is_default:
            await self._printers.clear_default_except(saved.id)

        await self._bus.publish(
            PrinterUpdated(printer_id=saved.id, name=saved.name, actor_id=actor.id)
        )
        await self._uow.commit()

        log.info(f"Updated printer {saved.name!r}, ID={saved.id}.")

        return PrinterMapper.to_result(saved)
