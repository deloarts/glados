"""
Unit tests for printing a PDF the browser rendered. What the actor got
wrong raises (no print permission, a calculation hidden from them, a file
that is not a PDF); a printer that cannot take the job becomes a failed
job row, as in the template print pipeline. No real sockets: the fake
gateway records what would have been sent.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.print_template_dto import PrintUploadedDocumentCommand
from src.modules.quality.application.services.uploaded_document_roots import UploadedDocumentRoots
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    MAX_BYTES,
)
from src.modules.quality.application.use_cases.print_document.print_uploaded_document import (
    PrintUploadedDocument,
)
from src.modules.quality.domain.entities.calculation import Calculation
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import PrintDocumentInvalidTypeError
from src.modules.quality.domain.errors import PrintDocumentTooLargeError
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from tests import factories
from tests.unit.fakes import FakeUnitOfWork

PDF = b"%PDF-1.7\n% report\n"


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may print documents unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.PRINT_DOCUMENTS]
    return factories.make_user(permissions=permissions, **overrides)


def make_printer(id: int = 1, kind: PrinterKind = PrinterKind.IPP_DOCUMENT) -> Printer:
    return Printer(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name="Office printer",
        internal_name=None,
        kind=kind,
        host="192.0.2.20",
        port=631,
        timeout_seconds=5.0,
        transport="ipp",
        ipp_uri_path="/",
        head_dpi=None,
        format_convert_factor=None,
        default_media=None,
        location=None,
        vendor=None,
        model=None,
        firmware=None,
        bought_item_ids=[],
        enabled=True,
        is_default=True,
        note=None,
        creator_id=1,
    )


def make_calculation(creator_id: int = 1, project_id: int | None = 7) -> Calculation:
    return Calculation(
        id=42,
        public_id=uuid4(),
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        tool="drive_sizing",
        title="Vertical axis",
        note=None,
        inputs={},
        results={},
        input_version=1,
        engine_version=1,
        project_id=project_id,
        product_id=None,
        creator_id=creator_id,
        released_at=None,
        released_by_id=None,
    )


class FakePrinterRepository:
    def __init__(self, printers: list[Printer]):
        self._printers = {p.id: p for p in printers}

    async def get_by_id(self, id: int) -> Printer | None:
        return self._printers.get(id)


class FakePrintJobRepository:
    def __init__(self) -> None:
        self.saved: list[PrintJob] = []

    async def save(self, item: PrintJob) -> PrintJob:
        item.id = len(self.saved) + 1
        self.saved.append(item)
        return item


class FakeCalculationRepository:
    def __init__(self, calculations: list[Calculation]):
        self._by_public_id = {c.public_id: c for c in calculations}

    async def get_by_public_id(self, public_id: UUID) -> Calculation | None:
        return self._by_public_id.get(public_id)


class FakeChecklistRepository:
    async def get_by_public_id(self, public_id: UUID) -> None:
        return None


class FakePrinterGateway:
    def __init__(
        self, delivery: PrintDelivery | None = None, raise_on_send: Exception | None = None
    ) -> None:
        self.sent: list[tuple[Printer, bytes, str, int, PrintSides]] = []
        self._delivery = delivery or PrintDelivery()
        self._raise_on_send = raise_on_send

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        if self._raise_on_send:
            raise self._raise_on_send
        self.sent.append((printer, payload, content_type, copies, sides))
        return self._delivery


class TestPrintUploadedDocument:
    def setup_method(self) -> None:
        self.calculation = make_calculation()
        self.printer = make_printer()
        self.jobs = FakePrintJobRepository()
        self.gateway = FakePrinterGateway()
        self.uow = FakeUnitOfWork()

    def use_case(self, printers: list[Printer] | None = None) -> PrintUploadedDocument:
        return PrintUploadedDocument(
            printer_repo=FakePrinterRepository(
                printers if printers is not None else [self.printer]
            ),  # type: ignore[arg-type]
            job_repo=self.jobs,  # type: ignore[arg-type]
            roots=UploadedDocumentRoots(
                FakeCalculationRepository([self.calculation]),  # type: ignore[arg-type]
                FakeChecklistRepository(),  # type: ignore[arg-type]
            ),
            gateway=self.gateway,
            uow=self.uow,
        )

    def command(self, **overrides: object) -> PrintUploadedDocumentCommand:
        values: dict[str, object] = {
            "document": "calculation_report",
            "root_public_id": self.calculation.public_id,
            "printer_id": self.printer.id,
            "copies": 2,
            "two_sided": False,
            "data": PDF,
        }
        return PrintUploadedDocumentCommand(**(values | overrides))

    async def test_print_uploaded_document_sends_the_pdf_and_writes_a_sent_job(self) -> None:
        result = await self.use_case().execute(make_user(), self.command())

        assert self.gateway.sent == [
            (self.printer, PDF, "application/pdf", 2, PrintSides.ONE_SIDED)
        ]
        assert result.status == "sent"
        assert result.attributes_substituted is False
        job = self.jobs.saved[0]
        assert (job.classifier, job.root_type, job.root_id) == (
            "calculation_report",
            "calculation",
            42,
        )
        assert job.template_id is None
        assert job.document_bytes == len(PDF)
        assert job.trigger == "manual"

    async def test_print_uploaded_document_two_sided_binds_on_the_long_edge(self) -> None:
        await self.use_case().execute(make_user(), self.command(two_sided=True))

        assert self.gateway.sent[0][4] is PrintSides.TWO_SIDED_LONG_EDGE

    async def test_print_uploaded_document_reports_substituted_settings(self) -> None:
        self.gateway = FakePrinterGateway(PrintDelivery(attributes_substituted=True))

        result = await self.use_case().execute(make_user(), self.command(two_sided=True))

        assert result.status == "sent"
        assert result.attributes_substituted is True

    async def test_print_uploaded_document_caps_copies(self) -> None:
        await self.use_case().execute(make_user(), self.command(copies=500))

        assert self.gateway.sent[0][3] == 10

    async def test_print_uploaded_document_ends_the_read_transaction_before_sending(
        self,
    ) -> None:
        commits_at_send: list[int] = []
        uow = self.uow

        class RecordingGateway(FakePrinterGateway):
            async def send(self, *args: object, **kwargs: object) -> PrintDelivery:
                commits_at_send.append(uow.commits)
                return PrintDelivery()

        self.gateway = RecordingGateway()
        await self.use_case().execute(make_user(), self.command())

        assert commits_at_send == [1]
        assert uow.commits == 2

    async def test_print_uploaded_document_needs_print_permission(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case().execute(make_user(permissions=[]), self.command())

        assert self.gateway.sent == []
        assert self.jobs.saved == []

    async def test_print_uploaded_document_hides_another_users_personal_calculation(
        self,
    ) -> None:
        self.calculation = make_calculation(creator_id=99, project_id=None)

        with pytest.raises(CalculationNotFoundError):
            await self.use_case().execute(make_user(), self.command())

        assert self.gateway.sent == []
        assert self.jobs.saved == []

    async def test_print_uploaded_document_unknown_calculation_raises(self) -> None:
        with pytest.raises(CalculationNotFoundError):
            await self.use_case().execute(make_user(), self.command(root_public_id=uuid4()))

    async def test_print_uploaded_document_rejects_a_file_that_is_not_a_pdf(self) -> None:
        with pytest.raises(PrintDocumentInvalidTypeError):
            await self.use_case().execute(make_user(), self.command(data=b"\x89PNG\r\n"))

        assert self.gateway.sent == []

    async def test_print_uploaded_document_rejects_a_file_over_the_limit(self) -> None:
        data = PDF + b"0" * MAX_BYTES

        with pytest.raises(PrintDocumentTooLargeError):
            await self.use_case().execute(make_user(), self.command(data=data))

    @pytest.mark.parametrize(
        ("printer", "message"),
        [
            (replace(make_printer(), archived=True), "archived"),
            (replace(make_printer(), enabled=False), "disabled"),
            (make_printer(kind=PrinterKind.ZPL_LABEL), "not a document printer"),
        ],
    )
    async def test_print_uploaded_document_unusable_printer_writes_a_failed_job(
        self, printer: Printer, message: str
    ) -> None:
        result = await self.use_case(printers=[printer]).execute(make_user(), self.command())

        assert self.gateway.sent == []
        assert result.status == "failed"
        assert result.error_message is not None and message in result.error_message
        assert result.printer_id == printer.id

    async def test_print_uploaded_document_missing_printer_writes_a_failed_job(self) -> None:
        result = await self.use_case(printers=[]).execute(make_user(), self.command())

        assert result.status == "failed"
        assert result.printer_id is None

    async def test_print_uploaded_document_unreachable_printer_writes_a_failed_job(
        self,
    ) -> None:
        self.gateway = FakePrinterGateway(raise_on_send=PrinterUnreachableError("timed out"))

        result = await self.use_case().execute(make_user(), self.command())

        assert result.status == "failed"
        assert result.error_message == "timed out"
        assert len(self.jobs.saved) == 1
