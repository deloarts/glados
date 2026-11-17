"""
Unit tests for DownloadPrintDocument: the "just a pdf download, no
printer involved at all" path. Unlike PrintDocument this raises on failure
(it's a single synchronous user action, not a fan-out that must degrade
gracefully), but it must never touch a printer gateway of any kind.
"""

from datetime import date

import pytest

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.use_cases.print_document.download_print_document import (
    DownloadPrintDocument,
)
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.errors import DocketSpecInvalidError
from src.modules.quality.domain.errors import PrintRootNotFoundError
from src.modules.quality.domain.errors import PrintTemplateNotConfiguredError
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.read.application.services.print_root_resolver import PrintRootResolver
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

_ZPL_TEMPLATE = "^XA^FO10,10^A0N,20,20^FD{value}^FS^XZ"
_DOCKET_SPEC = (
    '{"page": {"width_mm": 40, "height_mm": 40}, '
    '"blocks": [{"type": "text", "x": 2, "y": 2, "size_mm": 4, "field": "value"}]}'
)


def make_order_item(id: int = 1) -> OrderItem:
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
        line_type=OrderLineType.SOURCE,
        lot_position_id=None,
        source_item_id=1,
    )


def make_template(
    classifier: PrintClassifier = PrintClassifier.SOURCE_ITEM_LABEL,
    enabled: bool = True,
    source: str | None = _ZPL_TEMPLATE,
    field_map: dict[str, str] | None = None,
) -> PrintTemplate:
    return PrintTemplate(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        classifier=classifier,
        trigger=None,
        source=source,
        field_map=field_map if field_map is not None else {"value": "status"},
        printer_id=None,
        auto_print=False,
        copies_rule=PrintCopiesRule.FIXED,
        copies_fixed=1,
        max_copies=50,
        enabled=enabled,
        note=None,
        creator_id=None,
    )


class FakePrintTemplateRepository:
    def __init__(self, template: PrintTemplate | None = None):
        self._template = template

    async def get_by_classifier(self, classifier: str):
        if self._template and self._template.classifier == classifier:
            return self._template
        return None


class FakePrintJobRepository:
    def __init__(self):
        self.saved: list[PrintJob] = []

    async def save(self, item: PrintJob) -> PrintJob:
        item.id = len(self.saved) + 1
        self.saved.append(item)
        return item


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int):
        return self._items.get(id)

    def __getattr__(self, name):
        def _unimplemented(*args, **kwargs):
            raise NotImplementedError(name)

        return _unimplemented


class FakeDocketRenderer:
    def render_pdf(self, pages, *, paper):
        return b"%PDF-fake%", []

    def render_preview_png(self, pages):
        raise NotImplementedError

    def render_qr_png(self, payload, *, size_mm=25.0):
        raise NotImplementedError


def make_resolver(order_items: list[OrderItem] | None = None) -> PrintRootResolver:
    empty = FakeOrderItemRepository()
    return PrintRootResolver(
        order_repo=empty,
        order_item_repo=FakeOrderItemRepository(order_items),
        production_order_repo=empty,
        production_lot_repo=empty,
        made_item_repo=empty,
        bought_item_repo=empty,
        source_item_repo=empty,
    )


def make_use_case(template, order_items=None, job_repo=None) -> DownloadPrintDocument:
    return DownloadPrintDocument(
        FakePrintTemplateRepository(template),
        job_repo or FakePrintJobRepository(),
        make_resolver(order_items),
        docket_renderer=FakeDocketRenderer(),
        asset_resolver=None,
        domain_url="https://glados.test",
        uow=FakeUnitOfWork(),
    )


class TestDownloadPrintDocument:
    async def test_zpl_classifier_returns_rendered_zpl_bytes(self):
        job_repo = FakePrintJobRepository()
        use_case = make_use_case(
            make_template(), order_items=[make_order_item(1)], job_repo=job_repo
        )
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])

        rendered = await use_case.execute(actor, "source_item_label", "order_item", 1)

        assert rendered.content_type == "application/x-zpl"
        assert b"delivered" in rendered.payload
        assert job_repo.saved[0].status == "sent"
        assert job_repo.saved[0].printer_id is None
        assert job_repo.saved[0].trigger == "manual"

    async def test_docket_classifier_returns_pdf_bytes_with_no_printer_involved(self):
        job_repo = FakePrintJobRepository()
        template = make_template(
            classifier=PrintClassifier.MADE_ITEM_DOCKET,
            source=_DOCKET_SPEC,
            field_map={"value": "status"},
        )
        use_case = make_use_case(template, order_items=[make_order_item(1)], job_repo=job_repo)
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])

        rendered = await use_case.execute(actor, "made_item_docket", "order_item", 1)

        assert rendered.content_type == "application/pdf"
        assert rendered.payload == b"%PDF-fake%"
        assert job_repo.saved[0].printer_id is None
        assert job_repo.saved[0].document_bytes == len(b"%PDF-fake%")

    async def test_unprivileged_actor_raises_before_writing_a_job(self):
        job_repo = FakePrintJobRepository()
        use_case = make_use_case(make_template(), job_repo=job_repo)
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, "source_item_label", "order_item", 1)
        assert job_repo.saved == []

    async def test_missing_template_raises(self):
        use_case = make_use_case(None)
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        with pytest.raises(PrintTemplateNotFoundError):
            await use_case.execute(actor, "source_item_label", "order_item", 1)

    async def test_disabled_template_raises_not_configured(self):
        use_case = make_use_case(make_template(enabled=False))
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        with pytest.raises(PrintTemplateNotConfiguredError):
            await use_case.execute(actor, "source_item_label", "order_item", 1)

    async def test_empty_source_raises_not_configured(self):
        use_case = make_use_case(make_template(source=None))
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        with pytest.raises(PrintTemplateNotConfiguredError):
            await use_case.execute(actor, "source_item_label", "order_item", 1)

    async def test_missing_root_raises(self):
        use_case = make_use_case(make_template(), order_items=[])
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        with pytest.raises(PrintRootNotFoundError):
            await use_case.execute(actor, "source_item_label", "order_item", 999)

    async def test_malformed_docket_spec_raises_docket_spec_invalid(self):
        template = make_template(
            classifier=PrintClassifier.MADE_ITEM_DOCKET,
            source="{not json",
            field_map={"value": "status"},
        )
        use_case = make_use_case(template, order_items=[make_order_item(1)])
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        with pytest.raises(DocketSpecInvalidError):
            await use_case.execute(actor, "made_item_docket", "order_item", 1)

    async def test_no_job_written_when_rendering_fails(self):
        job_repo = FakePrintJobRepository()
        template = make_template(
            classifier=PrintClassifier.MADE_ITEM_DOCKET,
            source="{not json",
            field_map={"value": "status"},
        )
        use_case = make_use_case(template, order_items=[make_order_item(1)], job_repo=job_repo)
        actor = make_user(permissions=[Permission.PRINT_DOCUMENTS])
        with pytest.raises(DocketSpecInvalidError):
            await use_case.execute(actor, "made_item_docket", "order_item", 1)
        assert job_repo.saved == []
