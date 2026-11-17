"""
RenderPrintTemplateImage checks the permission itself:
PreviewPrintTemplate.execute is gated on print:documents, but the
PDF_DOCKET branch here never calls it, so gating only PreviewPrintTemplate
would leave docket previews open. The gate is the first statement of
RenderPrintTemplateImage.execute itself so it covers both branches
identically: this file proves both.
"""

from datetime import date

import pytest

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.use_cases.print_template.preview_print_template import (
    PreviewPrintTemplate,
)
from src.modules.quality.application.use_cases.print_template.render_print_template_image import (
    RenderPrintTemplateImage,
)
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.read.application.services.print_root_resolver import PrintRootResolver
from tests.factories import make_user

_ZPL_TEMPLATE = "^XA^FO10,10^A0N,20,20^FD{value}^FS^XZ"
_DOCKET_SPEC = (
    '{"page": {"width_mm": 40, "height_mm": 40}, '
    '"blocks": [{"type": "text", "x": 2, "y": 2, "size_mm": 4, "field": "value"}]}'
)


def make_actor(permissions: list[str] | None = None) -> User:
    if permissions is None:
        permissions = [Permission.PRINT_DOCUMENTS]
    return make_user(username="operator", full_name="Op Erator", permissions=permissions)


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


def make_template(classifier: PrintClassifier, source: str | None) -> PrintTemplate:
    return PrintTemplate(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        classifier=classifier,
        trigger=None,
        source=source,
        field_map={"value": "status"},
        printer_id=None,
        auto_print=False,
        copies_rule=PrintCopiesRule.FIXED,
        copies_fixed=1,
        max_copies=50,
        enabled=True,
        note=None,
        creator_id=None,
    )


class FakePrintTemplateRepository:
    def __init__(self, template: PrintTemplate | None):
        self._template = template

    async def get_by_classifier(self, classifier: str):
        if self._template and self._template.classifier == classifier:
            return self._template
        return None


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int):
        return self._items.get(id)

    def __getattr__(self, name):
        def _unimplemented(*args, **kwargs):
            raise NotImplementedError(name)

        return _unimplemented


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


class FakeRasterizer:
    def __init__(self) -> None:
        self.calls = 0

    def rasterize(self, zpl: str, *, design_dpi: int, format_convert_factor: int):
        self.calls += 1
        return b"zpl-png-bytes", []


class FakeDocketRenderer:
    def __init__(self) -> None:
        self.render_preview_png_calls = 0

    def render_pdf(self, pages, *, paper: str):
        raise NotImplementedError

    def render_preview_png(self, pages):
        self.render_preview_png_calls += 1
        return b"docket-png-bytes", []

    def render_qr_png(self, payload: str, *, size_mm: float = 25.0) -> bytes:
        raise NotImplementedError


class _Boom:
    """Any attribute access explodes, proves the permission check happens
    before any collaborator is touched."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"collaborator was used before the permission check ({name})")


def _preview_use_case(template_repo=None, resolver=None) -> PreviewPrintTemplate:
    return PreviewPrintTemplate(
        template_repo=template_repo if template_repo is not None else _Boom(),
        root_resolver=resolver if resolver is not None else _Boom(),
        domain_url="https://glados.test",
    )


class TestPermissionGate:
    async def test_actor_without_print_documents_cannot_render_zpl(self):
        rasterizer = FakeRasterizer()
        use_case = RenderPrintTemplateImage(
            template_repo=_Boom(),
            printer_repo=_Boom(),
            root_resolver=_Boom(),
            preview=_preview_use_case(),
            rasterizer=rasterizer,
            docket_renderer=_Boom(),
            asset_resolver=None,
            domain_url="https://glados.test",
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_actor(permissions=[]), "source_item_label", "order_item", 1)
        assert rasterizer.calls == 0

    async def test_actor_without_print_documents_cannot_render_docket(self):
        docket_renderer = FakeDocketRenderer()
        use_case = RenderPrintTemplateImage(
            template_repo=_Boom(),
            printer_repo=_Boom(),
            root_resolver=_Boom(),
            preview=_preview_use_case(),
            rasterizer=_Boom(),
            docket_renderer=docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_actor(permissions=[]), "made_item_docket", "order_item", 1)
        assert docket_renderer.render_preview_png_calls == 0


class TestPrintDocumentsActorCanRender:
    async def test_renders_a_zpl_label_to_png(self):
        rasterizer = FakeRasterizer()
        template_repo = FakePrintTemplateRepository(
            make_template(PrintClassifier.SOURCE_ITEM_LABEL, _ZPL_TEMPLATE)
        )
        resolver = make_resolver([make_order_item(1)])
        use_case = RenderPrintTemplateImage(
            template_repo=template_repo,
            printer_repo=_Boom(),  # printer_id is None, never touched
            root_resolver=resolver,
            preview=_preview_use_case(template_repo, resolver),
            rasterizer=rasterizer,
            docket_renderer=_Boom(),
            asset_resolver=None,
            domain_url="https://glados.test",
        )

        png, _warnings = await use_case.execute(make_actor(), "source_item_label", "order_item", 1)

        assert png == b"zpl-png-bytes"
        assert rasterizer.calls == 1

    async def test_renders_a_docket_to_png(self):
        docket_renderer = FakeDocketRenderer()
        template_repo = FakePrintTemplateRepository(
            make_template(PrintClassifier.MADE_ITEM_DOCKET, _DOCKET_SPEC)
        )
        resolver = make_resolver([make_order_item(1)])
        use_case = RenderPrintTemplateImage(
            template_repo=template_repo,
            printer_repo=_Boom(),
            root_resolver=resolver,
            preview=_preview_use_case(template_repo, resolver),
            rasterizer=_Boom(),
            docket_renderer=docket_renderer,
            asset_resolver=None,
            domain_url="https://glados.test",
        )

        png, _warnings = await use_case.execute(make_actor(), "made_item_docket", "order_item", 1)

        assert png == b"docket-png-bytes"
        assert docket_renderer.render_preview_png_calls == 1
