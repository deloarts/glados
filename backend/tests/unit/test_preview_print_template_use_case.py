"""
PreviewPrintTemplate is ZPL-only: a docket has no textual rendering, its
preview.png is the preview (see RenderPrintTemplateImage, which renders a
docket directly without going through this use case).
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
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.errors import PrintRootNotFoundError
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
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


class TestPreviewPrintTemplate:
    async def test_zpl_classifier_returns_rendered_text(self):
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(
                make_template(PrintClassifier.SOURCE_ITEM_LABEL, _ZPL_TEMPLATE)
            ),
            make_resolver([make_order_item(1)]),
            domain_url="https://glados.test",
        )
        result = await use_case.execute(make_actor(), "source_item_label", "order_item", 1)
        assert result.rendered_zpl is not None
        assert "delivered" in result.rendered_zpl
        assert result.warnings == []

    async def test_docket_classifier_returns_no_textual_rendering(self):
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(
                make_template(PrintClassifier.MADE_ITEM_DOCKET, _DOCKET_SPEC)
            ),
            make_resolver([make_order_item(1)]),
            domain_url="https://glados.test",
        )
        result = await use_case.execute(make_actor(), "made_item_docket", "order_item", 1)
        assert result.rendered_zpl is None
        assert result.warnings != []

    async def test_docket_classifier_does_not_touch_the_root_resolver(self):
        # No order item registered: if this reached root resolution it
        # would raise PrintRootNotFoundError; it must return early instead.
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(
                make_template(PrintClassifier.MADE_ITEM_DOCKET, _DOCKET_SPEC)
            ),
            make_resolver([]),
            domain_url="https://glados.test",
        )
        result = await use_case.execute(make_actor(), "made_item_docket", "order_item", 999)
        assert result.rendered_zpl is None

    async def test_missing_template_raises(self):
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(None), make_resolver(), domain_url="https://glados.test"
        )
        with pytest.raises(PrintTemplateNotFoundError):
            await use_case.execute(make_actor(), "source_item_label", "order_item", 1)

    async def test_empty_source_returns_no_rendering_with_a_warning(self):
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(make_template(PrintClassifier.SOURCE_ITEM_LABEL, None)),
            make_resolver(),
            domain_url="https://glados.test",
        )
        result = await use_case.execute(make_actor(), "source_item_label", "order_item", 1)
        assert result.rendered_zpl is None
        assert result.warnings != []

    async def test_missing_root_raises_for_zpl_classifier(self):
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(
                make_template(PrintClassifier.SOURCE_ITEM_LABEL, _ZPL_TEMPLATE)
            ),
            make_resolver([]),
            domain_url="https://glados.test",
        )
        with pytest.raises(PrintRootNotFoundError):
            await use_case.execute(make_actor(), "source_item_label", "order_item", 999)

    async def test_actor_without_print_documents_cannot_preview(self):
        use_case = PreviewPrintTemplate(
            FakePrintTemplateRepository(
                make_template(PrintClassifier.SOURCE_ITEM_LABEL, _ZPL_TEMPLATE)
            ),
            make_resolver([make_order_item(1)]),
            domain_url="https://glados.test",
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_actor(permissions=[]), "source_item_label", "order_item", 1)
