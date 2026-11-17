"""
The row locks and id pages of the lifecycle repositories, rendered for
Postgres, since the suite's SQLite ignores row locks: a lock re-reads the
rows FOR NO KEY UPDATE in ascending id order, a page is a keyset read of ids.
"""

from sqlalchemy.dialects import postgresql

# Loads every model, so the mappers that name each other by string configure.
import src.modules.platform.adapters.outbound.persistence.alembic_imports  # noqa: F401
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after_statement,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_statement,
)


def _sql(statement: object) -> str:
    compiled = statement.compile(  # type: ignore[attr-defined]
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return " ".join(str(compiled).split())


def test_a_lock_selects_the_rows_for_no_key_update_in_ascending_id_order() -> None:
    statement = lock_statement(ProductionLotOrmModel, ProductionLotOrmModel.id, [9, 3, 9, 5])

    sql = _sql(statement)

    assert "WHERE production_lot_table.id IN (3, 5, 9)" in sql
    assert sql.endswith("ORDER BY production_lot_table.id FOR NO KEY UPDATE")
    assert statement.get_execution_options()["populate_existing"] is True


def test_an_id_page_is_a_keyset_read() -> None:
    sql = _sql(ids_after_statement(OrderItemOrmModel.id, 120, 500))

    assert sql == (
        "SELECT order_item_table.id FROM order_item_table "
        "WHERE order_item_table.id > 120 ORDER BY order_item_table.id LIMIT 500"
    )
