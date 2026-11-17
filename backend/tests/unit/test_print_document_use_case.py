"""
Unit tests for the print pipeline. The central contract under test: except
for InsufficientPermissionsError, PrintDocument never raises. Every
pipeline failure becomes a status="failed" print_job row that comes back
as a normal result, never an exception. No real sockets: FakePrinterGateway
stands in for ZplSocketPrinterGateway/IppDocumentPrinterGateway.
"""

from datetime import date

import pytest

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from src.modules.quality.ports.outbound.repositories.print_job_repository import PrintJobFilterDto
from src.read.application.services.print_root_resolver import PrintRootResolver
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_order_item(id: int = 1, line_type: OrderLineType = OrderLineType.SOURCE) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.DELIVERED,
        quantity=10.0,
        quantity_delivered=10.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=line_type,
        lot_position_id=None,
        source_item_id=1,
    )


def make_printer(id: int = 1, kind: PrinterKind = PrinterKind.ZPL_LABEL) -> Printer:
    return Printer(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name="Zebra ZT230",
        internal_name="zebra-zt230",
        kind=kind,
        host="192.0.2.10",
        port=9100,
        timeout_seconds=5.0,
        transport="raw" if kind == "zpl_label" else "ipp",
        ipp_uri_path="/",
        head_dpi=300,
        format_convert_factor=1,
        default_media=None,
        location=None,
        vendor=None,
        model=None,
        firmware=None,
        bought_item_ids=[],
        enabled=True,
        is_default=False,
        note=None,
        creator_id=1,
    )


class FakePrintTemplateRepository:
    def __init__(self, template=None):
        self._template = template

    async def get_by_classifier(self, classifier: str):
        if self._template and self._template.classifier == classifier:
            return self._template
        return None

    async def get_all(self):
        return [self._template] if self._template else []

    async def get_armed_by_trigger(self, trigger: str):
        raise NotImplementedError

    async def save(self, item):
        self._template = item
        return item


class FakePrinterRepository:
    def __init__(self, printers: list[Printer] | None = None):
        self._printers = {p.id: p for p in (printers or [])}

    async def get_by_id(self, id: int):
        return self._printers.get(id)

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, item):
        raise NotImplementedError

    async def delete(self, item):
        raise NotImplementedError


class FakePrintJobRepository:
    def __init__(self):
        self.saved: list[PrintJob] = []
        self._next_id = 1

    async def save(self, item: PrintJob) -> PrintJob:
        item.id = self._next_id
        self._next_id += 1
        self.saved.append(item)
        return item

    async def get_multi(self, filters: PrintJobFilterDto):
        raise NotImplementedError

    async def claim_for_event(self, item: PrintJob) -> PrintJob | None:
        raise NotImplementedError

    async def finish_claimed(self, item: PrintJob) -> PrintJob:
        raise NotImplementedError

    async def release_claim(self, job_id: int) -> None:
        raise NotImplementedError


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int):
        return self._items.get(id)

    def __getattr__(self, name):
        def _unimplemented(*args, **kwargs):
            raise NotImplementedError(name)

        return _unimplemented


class FakePrinterGateway:
    def __init__(self, raise_on_send: Exception | None = None):
        self.sent: list[tuple] = []
        self._raise_on_send = raise_on_send

    async def send(
        self, printer, payload, content_type, copies, *, sides: PrintSides = PrintSides.ONE_SIDED
    ):
        if self._raise_on_send:
            raise self._raise_on_send
        self.sent.append((printer, payload, content_type, copies))
        return PrintDelivery()

    async def identify(self, printer):
        raise NotImplementedError

    async def status(self, printer):
        raise NotImplementedError


class FakeDocketRenderer:
    """Stands in for DocketRenderer, returning fixed bytes rather than
    actually rasterising, so these tests exercise the pipeline's dispatch
    and error handling, not Pillow."""

    def __init__(self):
        self.render_pdf_calls: list[tuple] = []

    def render_pdf(self, pages, *, paper):
        self.render_pdf_calls.append((pages, paper))
        return b"%PDF-fake%", []

    def render_preview_png(self, pages):
        return b"\x89PNG-fake", []

    def render_qr_png(self, payload, *, size_mm=25.0):
        return b"\x89PNG-qr-fake"


def make_resolver(order_items: list[OrderItem] | None = None) -> PrintRootResolver:
    empty = FakeOrderItemRepository()
    return PrintRootResolver(
        order_repo=empty,
        order_item_repo=FakeOrderItemRepository(order_items),
        production_order_repo=empty,  # unused by these tests; raises via __getattr__ if touched
        production_lot_repo=empty,
        made_item_repo=empty,
        bought_item_repo=empty,
        source_item_repo=empty,
    )


_ZPL_TEMPLATE = "^XA^FO10,10^A0N,20,20^FD{value}^FS^XZ"


_DOCKET_SPEC = (
    '{"page": {"width_mm": 40, "height_mm": 40}, '
    '"blocks": [{"type": "text", "x": 2, "y": 2, "size_mm": 4, "field": "value"}]}'
)


def make_template(
    classifier: PrintClassifier = PrintClassifier.SOURCE_ITEM_LABEL,
    enabled: bool = True,
    source: str | None = _ZPL_TEMPLATE,
    printer_id: int | None = 1,
    copies_fixed: int = 1,
    max_copies: int = 50,
    field_map: dict[str, str] | None = None,
    paper: str | None = None,
):
    from src.modules.quality.domain.entities.print_template import PrintTemplate

    return PrintTemplate(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        classifier=classifier,
        trigger=PrintTrigger.SOURCE_ITEM_DELIVERED,
        source=source,
        field_map=field_map if field_map is not None else {"value": "status"},
        printer_id=printer_id,
        auto_print=False,
        copies_rule=PrintCopiesRule.FIXED,
        copies_fixed=copies_fixed,
        max_copies=max_copies,
        paper=paper,
        enabled=enabled,
        note=None,
        creator_id=None,
    )


# ── PrintDocument ─────────────────────────────────────────────────────


class TestPrintDocument:
    def setup_method(self):
        self.order_item = make_order_item(id=1, line_type=OrderLineType.SOURCE)
        self.printer = make_printer(id=1, kind=PrinterKind.ZPL_LABEL)
        self.template_repo = FakePrintTemplateRepository(make_template())
        self.printer_repo = FakePrinterRepository([self.printer])
        self.job_repo = FakePrintJobRepository()
        self.resolver = make_resolver([self.order_item])
        self.gateway = FakePrinterGateway()
        self.docket_renderer = FakeDocketRenderer()
        self.actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        self.use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )

    async def test_successful_print_sends_and_writes_a_sent_job(self):
        result = await self.use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "sent"
        assert result.error_message is None
        assert len(self.gateway.sent) == 1
        assert self.job_repo.saved[0].status == "sent"

    async def test_the_read_transaction_ends_before_the_printer_is_contacted(self):
        """The read transaction commits before the slow or offline printer is
        contacted, and the job row is written and committed in a second
        transaction only once the send's outcome is known."""
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

        class RecordingJobRepository(FakePrintJobRepository):
            async def save(self, item):
                events.append("save")
                return await super().save(item)

        job_repo = RecordingJobRepository()
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            job_repo,
            self.resolver,
            gateway=RecordingGateway(),
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=RecordingUow(),
        )

        await use_case.execute(self.actor, "source_item_label", "order_item", 1)

        assert events == ["commit", "send", "save", "commit"]
        assert job_repo.saved[0].status == "sent"

    async def test_rendered_zpl_contains_the_substituted_field(self):
        await self.use_case.execute(self.actor, "source_item_label", "order_item", 1)
        _, payload, content_type, _ = self.gateway.sent[0]
        assert content_type == "application/x-zpl"
        assert b"delivered" in payload  # order_item.status == "delivered"

    async def test_unprivileged_actor_raises_immediately_with_no_job_written(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor, "source_item_label", "order_item", 1)
        assert self.job_repo.saved == []

    async def test_an_auto_print_does_not_need_the_actor_to_hold_print_documents(self):
        # PRINT_DOCUMENTS gates *choosing* to print. An auto-print was
        # authorised when an admin armed the template; the operator who
        # recorded the delivery never asked for it, and their shop-floor
        # action must not fail because they cannot print manually.
        actor = make_user(permissions=[])

        result = await self.use_case.execute(
            actor, "source_item_label", "order_item", 1, trigger="auto", source_event_id="1700-0"
        )

        assert result.status == "sent"
        assert self.job_repo.saved[0].trigger == "auto"
        assert self.job_repo.saved[0].actor_id == actor.id  # still attributed to them

    async def test_missing_template_writes_a_failed_job_not_a_raise(self):
        self.template_repo = FakePrintTemplateRepository(None)
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"
        assert "No print template" in (result.error_message or "")
        assert self.gateway.sent == []

    async def test_disabled_template_writes_a_failed_job_not_a_raise(self):
        self.template_repo = FakePrintTemplateRepository(make_template(enabled=False))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"
        assert self.gateway.sent == []

    async def test_missing_printer_writes_a_failed_job(self):
        self.template_repo = FakePrintTemplateRepository(make_template(printer_id=999))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"
        assert "not found" in (result.error_message or "")

    async def test_no_printer_configured_and_no_override_writes_a_failed_job(self):
        self.template_repo = FakePrintTemplateRepository(make_template(printer_id=None))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"

    async def test_printer_kind_mismatch_writes_a_failed_job_not_a_raise(self):
        # Classifier needs zpl_label, but the assigned printer is ipp_document.
        # This is the exact guardrail that stops a label hitting the
        # wrong transport, and it must not crash the request.
        ipp_printer = make_printer(id=2, kind=PrinterKind.IPP_DOCUMENT)
        self.printer_repo = FakePrinterRepository([ipp_printer])
        self.template_repo = FakePrintTemplateRepository(make_template(printer_id=2))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"
        assert "ipp_document" in (result.error_message or "")
        assert self.gateway.sent == []

    @pytest.mark.parametrize(
        ("change", "reason"), [({"enabled": False}, "disabled"), ({"archived": True}, "archived")]
    )
    async def test_out_of_use_printer_writes_a_failed_job_and_sends_nothing(
        self, change: dict[str, bool], reason: str
    ):
        # Disabling a printer, or Disable All Printers, must stop its labels
        # and dockets, not only uploaded reports.
        for field, value in change.items():
            setattr(self.printer, field, value)
        result = await self.use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"
        assert reason in (result.error_message or "")
        assert self.gateway.sent == []
        assert self.job_repo.saved[0].status == "failed"

    async def test_missing_root_writes_a_failed_job(self):
        result = await self.use_case.execute(self.actor, "source_item_label", "order_item", 999)
        assert result.status == "failed"
        assert "not found" in (result.error_message or "")

    async def test_unreachable_printer_writes_a_failed_job_not_a_raise(self):
        from src.modules.quality.domain.errors import PrinterUnreachableError

        self.gateway = FakePrinterGateway(raise_on_send=PrinterUnreachableError("no route"))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.status == "failed"
        assert "no route" in (result.error_message or "")

    async def test_copies_default_to_template_copies_fixed(self):
        self.template_repo = FakePrintTemplateRepository(make_template(copies_fixed=3))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.copies == 3
        assert self.gateway.sent[0][3] == 3

    async def test_explicit_copies_override_template_default(self):
        result = await self.use_case.execute(
            self.actor, "source_item_label", "order_item", 1, copies=7
        )
        assert result.copies == 7

    async def test_copies_are_capped_at_max_copies(self):
        self.template_repo = FakePrintTemplateRepository(make_template(max_copies=5))
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(
            self.actor, "source_item_label", "order_item", 1, copies=500
        )
        assert result.copies == 5

    async def test_printer_id_override_takes_precedence_over_template_default(self):
        other_printer = make_printer(id=2, kind=PrinterKind.ZPL_LABEL)
        self.printer_repo = FakePrinterRepository([self.printer, other_printer])
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(
            self.actor, "source_item_label", "order_item", 1, printer_id=2
        )
        assert result.printer_id == 2

    async def test_job_records_actor_and_trigger(self):
        result = await self.use_case.execute(self.actor, "source_item_label", "order_item", 1)
        assert result.actor_id == self.actor.id
        assert result.trigger == "manual"

    async def test_docket_classifier_renders_pdf_and_sends_to_any_ipp_document_printer(self):
        # made_item_docket is PDF_DOCKET -> requires an "ipp_document" printer,
        # not a hardcoded model; any printer of that kind must work.
        ipp_printer = make_printer(id=2, kind=PrinterKind.IPP_DOCUMENT)
        self.printer_repo = FakePrinterRepository([ipp_printer])
        self.template_repo = FakePrintTemplateRepository(
            make_template(
                classifier=PrintClassifier.MADE_ITEM_DOCKET,
                source=_DOCKET_SPEC,
                field_map={"value": "status"},
                printer_id=2,
                paper="a4",
            )
        )
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "made_item_docket", "order_item", 1)
        assert result.status == "sent"
        assert len(self.gateway.sent) == 1
        _, payload, content_type, _ = self.gateway.sent[0]
        assert content_type == "application/pdf"
        assert payload == b"%PDF-fake%"
        assert self.job_repo.saved[0].document_bytes == len(b"%PDF-fake%")
        assert self.job_repo.saved[0].rendered_zpl is None
        assert len(self.docket_renderer.render_pdf_calls) == 1
        pages, paper = self.docket_renderer.render_pdf_calls[0]
        assert paper == "a4"
        # A docket with no positions table is still exactly one page.
        assert len(pages) == 1

    async def test_malformed_docket_spec_writes_a_failed_job_not_a_raise(self):
        ipp_printer = make_printer(id=2, kind=PrinterKind.IPP_DOCUMENT)
        self.printer_repo = FakePrinterRepository([ipp_printer])
        self.template_repo = FakePrintTemplateRepository(
            make_template(
                classifier=PrintClassifier.MADE_ITEM_DOCKET,
                source="{not valid json",
                field_map={"value": "status"},
                printer_id=2,
            )
        )
        use_case = PrintDocument(
            self.template_repo,
            self.printer_repo,
            self.job_repo,
            self.resolver,
            gateway=self.gateway,
            docket_renderer=self.docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
            uow=FakeUnitOfWork(),
        )
        result = await use_case.execute(self.actor, "made_item_docket", "order_item", 1)
        assert result.status == "failed"
        assert self.gateway.sent == []
