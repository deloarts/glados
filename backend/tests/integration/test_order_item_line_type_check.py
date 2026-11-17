"""
The only proof layer 1 (the DB CHECK,
ck_order_item_line_type) is actually live. Domain-rule and use-case level
tests (test_order_rules_line_type.py,
tests/unit/order/test_order_item_line_type.py, tests/unit/production_lot/)
prove layers 2/3 but a Python-level
assertion running before every save can't demonstrate the constraint
itself exists in the schema. Same style as test_soft_delete_uniqueness.py:
asserts against the schema directly via a raw ORM insert, not through the
API. Integration tests create the schema from `Base.metadata` (see
conftest.py's `_schema` fixture), which includes every model's
`__table_args__`, so this exercises the real constraint SQLite enforces
too, not just Postgres.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)


async def _row(db: Session, **overrides: object) -> None:
    defaults: dict[str, object] = {
        "created": datetime.now(UTC),
        "changes": [],
        "status": "ordered",
        "quantity": 1.0,
        "unit": "pcs",
        "items_per_unit": 1.0,
        "creator_id": 1,
        "order_id": 1,
        "supplier_id": 1,
        "project_id": 1,
        "line_type": "BOUGHT",
        "bought_item_id": 1,
    }
    db.add(OrderItemOrmModel(**(defaults | overrides)))
    await db.commit()


async def test_a_valid_bought_line_is_accepted(db: Session) -> None:
    await _row(db, line_type="BOUGHT", bought_item_id=1)


async def test_a_bought_line_with_no_bought_item_id_is_rejected(db: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_order_item_line_type"):
        await _row(db, line_type="BOUGHT", bought_item_id=None)


async def test_a_bought_line_with_a_source_item_id_too_is_rejected(db: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_order_item_line_type"):
        await _row(db, line_type="BOUGHT", bought_item_id=1, source_item_id=2)


async def test_a_virtual_line_with_no_virtual_name_is_rejected(db: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_order_item_line_type"):
        await _row(db, line_type="VIRTUAL", bought_item_id=None, virtual_name=None)


async def test_a_made_line_with_no_lot_position_id_is_rejected(db: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_order_item_line_type"):
        await _row(db, line_type="MADE", bought_item_id=None, lot_position_id=None)
