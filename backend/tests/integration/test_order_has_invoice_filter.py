"""
The order list's `has_invoice` filter keeps orders with at least one
`invoice` file (True) or with none (False) and leaves the file table out of
the query when unset. An order may carry several invoices, so the positive
branch is an EXISTS, never a join that would duplicate rows. Reuses the
order builders from test_order_item_naming.py.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.adapters.outbound.persistence.models.order_file_model import (
    OrderFileOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from tests.integration.test_order_item_naming import _order


def _file(db, *, order_id: int, category: OrderFileCategory, stored_name: str) -> None:
    db.add(
        OrderFileOrmModel(
            order_id=order_id,
            file_name=f"{stored_name}.pdf",
            stored_name=stored_name,
            mime_type="application/pdf",
            size_bytes=1,
            storage_path=f"orders/{order_id}/pdf/{stored_name}",
            sha256=stored_name,
            category=category.value,
            created=datetime.now(UTC),
            uploaded_by_user_id=1,
        )
    )


async def _three_orders(db) -> None:
    """O-1 has two invoices, O-2 only a delivery note, O-3 no files."""
    _order(db, order_id=1)
    _order(db, order_id=2)
    _order(db, order_id=3)
    await db.commit()
    _file(db, order_id=1, category=OrderFileCategory.INVOICE, stored_name="inv-1a")
    _file(db, order_id=1, category=OrderFileCategory.INVOICE, stored_name="inv-1b")
    _file(db, order_id=2, category=OrderFileCategory.DELIVERY_NOTE, stored_name="dn-2")
    await db.commit()


class TestHasInvoiceFilter:
    async def test_true_keeps_only_orders_with_an_invoice_and_does_not_duplicate(self, db):
        await _three_orders(db)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(has_invoice=True)
        )

        assert total == 1
        assert [o.order_number for o in orders] == ["O-1"]

    async def test_false_keeps_only_orders_without_an_invoice(self, db):
        await _three_orders(db)

        total, orders = await SqlAlchemyOrderRepository(db).get_multi(
            OrderFilterDto(has_invoice=False)
        )

        assert total == 2
        assert sorted(o.order_number for o in orders) == ["O-2", "O-3"]

    async def test_unset_returns_every_order(self, db):
        await _three_orders(db)

        total, _ = await SqlAlchemyOrderRepository(db).get_multi(OrderFilterDto())

        assert total == 3
