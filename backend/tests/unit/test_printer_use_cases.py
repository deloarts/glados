"""
Unit tests for printer catalogue use cases (create, update, delete, get,
test-print, status). No database, no HTTP, no real sockets. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.printer_dto import CreatePrinterCommand
from src.modules.quality.application.dto.printer_dto import UpdatePrinterCommand
from src.modules.quality.application.use_cases.printer.archive_printer import ArchivePrinter
from src.modules.quality.application.use_cases.printer.create_printer import CreatePrinter
from src.modules.quality.application.use_cases.printer.get_printer import GetPrinter
from src.modules.quality.application.use_cases.printer.get_printer import GetPrinters
from src.modules.quality.application.use_cases.printer.get_printer_status import GetPrinterStatus
from src.modules.quality.application.use_cases.printer.restore_printer import RestorePrinter
from src.modules.quality.application.use_cases.printer.test_print_printer import TestPrintPrinter
from src.modules.quality.application.use_cases.printer.update_printer import UpdatePrinter
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.events.printer_events import PrinterArchived
from src.modules.quality.domain.events.printer_events import PrinterCreated
from src.modules.quality.domain.events.printer_events import PrinterRestored
from src.modules.quality.domain.events.printer_events import PrinterUpdated
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from src.modules.quality.ports.outbound.repositories.printer_repository import PrinterFilterDto
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_bought_item(id: int = 1) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name="Label roll 70x32mm",
        order_code_1="LBL-7032",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.WEB,
        part_number=None,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
    )


def make_printer(
    id: int = 1,
    name: str = "Zebra ZT230",
    internal_name: str = "zebra-zt230",
    kind: PrinterKind = PrinterKind.ZPL_LABEL,
    archived: bool = False,
    bought_item_ids: list[int] | None = None,
) -> Printer:
    return Printer(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        archived=archived,
        name=name,
        internal_name=internal_name,
        kind=kind,
        host="192.0.2.10",
        port=9100,
        timeout_seconds=5.0,
        transport="raw",
        ipp_uri_path="/",
        head_dpi=300,
        format_convert_factor=2,
        default_media=None,
        location="Shop floor",
        vendor="Zebra",
        model="ZT230",
        firmware=None,
        bought_item_ids=bought_item_ids if bought_item_ids is not None else [],
        enabled=True,
        is_default=False,
        note=None,
        creator_id=1,
    )


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakePrinterRepository:
    def __init__(self, printers: list[Printer] | None = None):
        self._printers: dict[int, Printer] = {}
        self._next_id = 1
        for p in printers or []:
            self._printers[p.id] = p
            self._next_id = max(self._next_id, p.id + 1)

    async def get_by_id(self, id: int) -> Printer | None:
        return self._printers.get(id)

    async def get_multi(self, filters: PrinterFilterDto) -> tuple[int, list[Printer]]:
        items = list(self._printers.values())
        if not filters.include_archived:
            items = [p for p in items if not p.archived]
        if filters.id is not None:
            items = [p for p in items if p.id == filters.id]
        if filters.kind is not None:
            items = [p for p in items if p.kind == filters.kind]
        total = len(items)
        skip = filters.skip or 0
        limit = filters.limit
        return total, items[skip : skip + limit if limit else None]

    async def save(self, item: Printer) -> Printer:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._printers[item.id] = item
        return item

    async def delete(self, item: Printer) -> None:
        item.archived = True
        await self.save(item)

    async def clear_default_except(self, id: int) -> None:
        for printer in self._printers.values():
            if printer.id != id:
                printer.is_default = False


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        raise NotImplementedError

    async def get_multi(self, filters: BoughtItemFilterDto) -> tuple[int, list[BoughtItem]]:
        raise NotImplementedError

    async def save(self, item: BoughtItem) -> BoughtItem:
        raise NotImplementedError

    async def delete(self, item: BoughtItem) -> None:
        raise NotImplementedError

    async def merge_demand_items(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError

    async def merge_order_items(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError

    async def merge_article_groups(self, source_id: int, target_id: int) -> None:
        raise NotImplementedError


class FakePrinterGateway:
    """Records calls instead of touching a socket."""

    def __init__(self):
        self.sent: list[tuple[Printer, bytes, str, int]] = []
        self.identify_calls: list[Printer] = []
        self.status_calls: list[Printer] = []

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        self.sent.append((printer, payload, content_type, copies))
        return PrintDelivery()

    async def identify(self, printer: Printer) -> str:
        self.identify_calls.append(printer)
        return "ZT230-300dpi,V72.20.01Z,12,4096KB"

    async def status(self, printer: Printer) -> list[str]:
        self.status_calls.append(printer)
        return ["paper out:      no", "paused:         no"]


# ── CreatePrinter ─────────────────────────────────────────────────────


class TestCreatePrinter:
    def setup_method(self):
        self.printer_repo = FakePrinterRepository()
        self.bought_item_repo = FakeBoughtItemRepository([make_bought_item(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_PRINTERS])
        self.bus = FakeEventBus()
        self.use_case = CreatePrinter(
            self.printer_repo, self.bought_item_repo, event_bus=self.bus, uow=FakeUnitOfWork()
        )

    def _cmd(self, **kwargs) -> CreatePrinterCommand:
        defaults = dict(
            name="Zebra ZT230",
            internal_name="zebra-zt230",
            kind="zpl_label",
            host="192.0.2.10",
            port=9100,
            transport="raw",
        )
        defaults.update(kwargs)
        return CreatePrinterCommand(**defaults)

    async def test_creates_printer_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.name == "Zebra ZT230"
        assert result.id > 0

    async def test_creates_printer_with_bought_item_ids(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(bought_item_ids=[1]))
        assert result.bought_item_ids == [1]

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        (event,) = self.bus.published
        assert isinstance(event, PrinterCreated)
        assert event.printer_id == result.id
        assert event.name == "Zebra ZT230"
        assert event.actor_id == self.actor.id

    async def test_duplicate_internal_name_is_allowed(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(name="Second Zebra"))
        assert result.internal_name == "zebra-zt230"

    async def test_internal_name_is_optional(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(internal_name=None))
        assert result.internal_name is None

    async def test_creating_a_default_clears_the_previous_default(self):
        previous = make_printer(id=7)
        previous.is_default = True
        await self.printer_repo.save(previous)

        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(is_default=True))

        assert result.is_default is True
        assert previous.is_default is False

    async def test_creating_a_non_default_keeps_the_existing_default(self):
        previous = make_printer(id=7)
        previous.is_default = True
        await self.printer_repo.save(previous)

        await self.use_case.execute(actor=self.actor, cmd=self._cmd(is_default=False))

        assert previous.is_default is True

    async def test_missing_bought_item_raises(self):
        with pytest.raises(BoughtItemNotFoundError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(bought_item_ids=[999]))

    async def test_unprivileged_cannot_create(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


# ── UpdatePrinter ─────────────────────────────────────────────────────


class TestUpdatePrinter:
    def setup_method(self):
        self.printer = make_printer(id=1)
        self.printer_repo = FakePrinterRepository([self.printer])
        self.bought_item_repo = FakeBoughtItemRepository([make_bought_item(id=1)])
        self.actor = make_user(permissions=[Permission.WRITE_PRINTERS])
        self.bus = FakeEventBus()
        self.use_case = UpdatePrinter(
            self.printer_repo, self.bought_item_repo, event_bus=self.bus, uow=FakeUnitOfWork()
        )

    async def test_updates_partial_fields_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(name="Zebra ZT230 (Line 2)")
        )
        assert result.name == "Zebra ZT230 (Line 2)"

    async def test_updates_bought_item_ids(self):
        result = await self.use_case.execute(
            actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(bought_item_ids=[1])
        )
        assert result.bought_item_ids == [1]

    async def test_kind_reaches_the_entity_as_the_enum(self):
        """The endpoint builds the command from plain JSON strings, and the
        repository writes the kind through its enum value."""
        await self.use_case.execute(
            actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(kind="ipp_document")
        )
        assert self.printer.kind is PrinterKind.IPP_DOCUMENT

    async def test_setting_a_default_clears_the_previous_default(self):
        previous = make_printer(id=2)
        previous.is_default = True
        await self.printer_repo.save(previous)

        result = await self.use_case.execute(
            actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(is_default=True)
        )

        assert result.is_default is True
        assert previous.is_default is False

    async def test_updating_another_field_keeps_the_existing_default(self):
        previous = make_printer(id=2)
        previous.is_default = True
        await self.printer_repo.save(previous)

        await self.use_case.execute(
            actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(name="Renamed")
        )

        assert previous.is_default is True

    async def test_missing_bought_item_raises(self):
        with pytest.raises(BoughtItemNotFoundError):
            await self.use_case.execute(
                actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(bought_item_ids=[999])
            )

    async def test_renaming_to_own_internal_name_is_a_no_op(self):
        result = await self.use_case.execute(
            actor=self.actor,
            printer_id=1,
            cmd=UpdatePrinterCommand(internal_name="zebra-zt230"),
        )
        assert result.internal_name == "zebra-zt230"

    async def test_duplicate_internal_name_is_allowed(self):
        await self.printer_repo.save(make_printer(id=2, internal_name="bizhub-c251i"))
        result = await self.use_case.execute(
            actor=self.actor,
            printer_id=1,
            cmd=UpdatePrinterCommand(internal_name="bizhub-c251i"),
        )
        assert result.internal_name == "bizhub-c251i"

    async def test_event_carries_correct_fields(self):
        result = await self.use_case.execute(
            actor=self.actor, printer_id=1, cmd=UpdatePrinterCommand(name="Renamed")
        )
        (event,) = self.bus.published
        assert isinstance(event, PrinterUpdated)
        assert event.printer_id == result.id
        assert event.name == "Renamed"

    async def test_not_found_raises(self):
        with pytest.raises(PrinterNotFoundError):
            await self.use_case.execute(
                actor=self.actor, printer_id=999, cmd=UpdatePrinterCommand()
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, printer_id=1, cmd=UpdatePrinterCommand())


# ── ArchivePrinter / RestorePrinter ────────────────────────────────────


class TestArchivePrinter:
    def setup_method(self):
        self.printer = make_printer(id=1)
        self.printer_repo = FakePrinterRepository([self.printer])
        self.actor = make_user(permissions=[Permission.WRITE_PRINTERS])
        self.bus = FakeEventBus()
        self.use_case = ArchivePrinter(self.printer_repo, event_bus=self.bus, uow=FakeUnitOfWork())

    async def test_archives_successfully(self):
        result = await self.use_case.execute(actor=self.actor, printer_id=1)
        assert result.archived is True

    async def test_archiving_twice_is_idempotent(self):
        await self.use_case.execute(actor=self.actor, printer_id=1)
        result = await self.use_case.execute(actor=self.actor, printer_id=1)
        assert result.archived is True

    async def test_archived_printer_excluded_from_get_multi_by_default(self):
        await self.use_case.execute(actor=self.actor, printer_id=1)
        total, items = await self.printer_repo.get_multi(PrinterFilterDto())
        assert total == 0
        assert items == []

    async def test_archived_printer_included_when_requested(self):
        await self.use_case.execute(actor=self.actor, printer_id=1)
        total, _items = await self.printer_repo.get_multi(PrinterFilterDto(include_archived=True))
        assert total == 1

    async def test_archived_printer_still_resolves_by_id(self):
        await self.use_case.execute(actor=self.actor, printer_id=1)
        assert await self.printer_repo.get_by_id(1) is not None

    async def test_event_carries_correct_fields(self):
        await self.use_case.execute(actor=self.actor, printer_id=1)
        (event,) = self.bus.published
        assert isinstance(event, PrinterArchived)
        assert event.printer_id == 1

    async def test_not_found_raises(self):
        with pytest.raises(PrinterNotFoundError):
            await self.use_case.execute(actor=self.actor, printer_id=999)

    async def test_unprivileged_cannot_archive(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, printer_id=1)


class TestRestorePrinter:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_PRINTERS])
        self.bus = FakeEventBus()

    async def test_restores_successfully(self):
        printer = make_printer(id=1, archived=True)
        repo = FakePrinterRepository([printer])
        result = await RestorePrinter(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
            actor=self.actor, printer_id=1
        )
        assert result.archived is False

    async def test_restoring_twice_is_idempotent(self):
        printer = make_printer(id=1, archived=True)
        repo = FakePrinterRepository([printer])
        use_case = RestorePrinter(repo, event_bus=self.bus, uow=FakeUnitOfWork())
        await use_case.execute(actor=self.actor, printer_id=1)
        result = await use_case.execute(actor=self.actor, printer_id=1)
        assert result.archived is False

    async def test_event_carries_correct_fields(self):
        printer = make_printer(id=1, archived=True)
        repo = FakePrinterRepository([printer])
        await RestorePrinter(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
            actor=self.actor, printer_id=1
        )
        (event,) = self.bus.published
        assert isinstance(event, PrinterRestored)
        assert event.printer_id == 1

    async def test_not_found_raises(self):
        repo = FakePrinterRepository([])
        with pytest.raises(PrinterNotFoundError):
            await RestorePrinter(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
                actor=self.actor, printer_id=999
            )

    async def test_unprivileged_cannot_restore(self):
        printer = make_printer(id=1, archived=True)
        repo = FakePrinterRepository([printer])
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await RestorePrinter(repo, event_bus=self.bus, uow=FakeUnitOfWork()).execute(
                actor=actor, printer_id=1
            )


# ── GetPrinter / GetPrinters ──────────────────────────────────────────


class TestGetPrinter:
    def setup_method(self):
        self.printer_repo = FakePrinterRepository([make_printer(id=1)])
        self.use_case = GetPrinter(self.printer_repo)

    async def test_returns_printer_when_found(self):
        result = await self.use_case.execute(printer_id=1)
        assert result.id == 1
        assert result.name == "Zebra ZT230"

    async def test_not_found_raises(self):
        with pytest.raises(PrinterNotFoundError):
            await self.use_case.execute(printer_id=999)


class TestGetPrinters:
    def setup_method(self):
        self.printer_repo = FakePrinterRepository(
            [
                make_printer(id=1, name="Zebra ZT230", kind=PrinterKind.ZPL_LABEL),
                make_printer(
                    id=2, name="bizhub C251i", internal_name="bizhub", kind=PrinterKind.IPP_DOCUMENT
                ),
            ]
        )
        self.use_case = GetPrinters(self.printer_repo)

    async def test_lists_all_printers(self):
        result = await self.use_case.execute(PrinterFilterDto())
        assert result.total == 2

    async def test_filters_by_kind(self):
        result = await self.use_case.execute(PrinterFilterDto(kind="ipp_document"))
        assert result.total == 1
        assert result.items[0].name == "bizhub C251i"


# ── TestPrintPrinter ──────────────────────────────────────────────────


class TestTestPrintPrinter:
    def setup_method(self):
        self.printer_repo = FakePrinterRepository([make_printer(id=1, kind=PrinterKind.ZPL_LABEL)])
        self.gateway = FakePrinterGateway()
        self.actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        self.use_case = TestPrintPrinter(self.printer_repo, gateway=self.gateway)

    async def test_sends_zpl_self_test_for_zpl_printer(self):
        await self.use_case.execute(actor=self.actor, printer_id=1)
        (call,) = self.gateway.sent
        _, payload, content_type, copies = call
        assert content_type == "application/x-zpl"
        assert copies == 1
        assert b"^XA" in payload and b"^XZ" in payload

    async def test_the_read_transaction_ends_before_the_printer_is_contacted(self):
        events = []

        class RecordingUow:
            async def commit(self):
                events.append("commit")

            async def rollback(self):
                events.append("rollback")

        class RecordingGateway(FakePrinterGateway):
            async def send(self, printer, payload, content_type, copies):
                events.append("send")
                await super().send(printer, payload, content_type, copies)

        await TestPrintPrinter(
            self.printer_repo, gateway=RecordingGateway(), uow=RecordingUow()
        ).execute(actor=self.actor, printer_id=1)

        assert events == ["commit", "send"]

    async def test_sends_pdf_self_test_for_ipp_printer(self):
        await self.printer_repo.save(
            make_printer(id=2, internal_name="bizhub", kind=PrinterKind.IPP_DOCUMENT)
        )
        await self.use_case.execute(actor=self.actor, printer_id=2)
        (call,) = self.gateway.sent
        _, payload, content_type, _copies = call
        assert content_type == "application/pdf"
        assert payload.startswith(b"%PDF")

    async def test_not_found_raises(self):
        with pytest.raises(PrinterNotFoundError):
            await self.use_case.execute(actor=self.actor, printer_id=999)

    async def test_unprivileged_cannot_print(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, printer_id=1)


# ── GetPrinterStatus ──────────────────────────────────────────────────


class TestGetPrinterStatus:
    def setup_method(self):
        self.printer_repo = FakePrinterRepository([make_printer(id=1)])
        self.gateway = FakePrinterGateway()
        self.use_case = GetPrinterStatus(self.printer_repo, gateway=self.gateway)
        self.actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])

    async def test_returns_identity_and_status(self):
        result = await self.use_case.execute(actor=self.actor, printer_id=1)
        assert "ZT230" in result.identity
        assert any("paper out" in line for line in result.status_lines)

    async def test_not_found_raises(self):
        with pytest.raises(PrinterNotFoundError):
            await self.use_case.execute(actor=self.actor, printer_id=999)

    async def test_unprivileged_cannot_read_status(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, printer_id=1)
        assert self.gateway.status_calls == []

    async def test_print_documents_actor_reads_status(self):
        result = await self.use_case.execute(actor=self.actor, printer_id=1)
        assert result.identity != ""
