"""Use case for creating a new printer and publishing the PrinterCreated event."""

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.application.dto.printer_dto import CreatePrinterCommand
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.application.mappers.printer_mapper import PrinterMapper
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.events.printer_events import PrinterCreated
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreatePrinter:
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

    async def execute(self, actor: User, cmd: CreatePrinterCommand) -> PrinterResult:
        PrinterRules.assert_can_create(actor)
        PrinterRules.assert_host_allowed(cmd.host)

        for bought_item_id in cmd.bought_item_ids:
            if not await self._bought_items.get_by_id(bought_item_id):
                raise BoughtItemNotFoundError(f"Bought item #{bought_item_id} not found.")

        now = now_utc()
        printer = Printer(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Printer created."),
            archived=False,
            name=cmd.name,
            internal_name=cmd.internal_name,
            kind=PrinterKind(cmd.kind),
            host=cmd.host,
            port=cmd.port,
            timeout_seconds=cmd.timeout_seconds,
            transport=cmd.transport,
            ipp_uri_path=cmd.ipp_uri_path,
            head_dpi=cmd.head_dpi,
            format_convert_factor=cmd.format_convert_factor,
            default_media=cmd.default_media,
            location=cmd.location,
            vendor=cmd.vendor,
            model=cmd.model,
            firmware=cmd.firmware,
            bought_item_ids=cmd.bought_item_ids,
            enabled=cmd.enabled,
            is_default=cmd.is_default,
            note=cmd.note,
            creator_id=actor.id,
            creator_full_name=actor.full_name,
        )

        saved = await self._printers.save(printer)

        await self._bus.publish(
            PrinterCreated(printer_id=saved.id, name=saved.name, actor_id=actor.id)
        )
        await self._uow.commit()

        log.info(f"Created printer {saved.name!r}, ID={saved.id}.")

        return PrinterMapper.to_result(saved)
