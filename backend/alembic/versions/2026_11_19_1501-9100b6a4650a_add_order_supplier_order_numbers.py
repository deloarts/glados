"""add order supplier order numbers

Revision ID: 9100b6a4650a
Revises: 0dcb223dd17a
Create Date: 2026-11-19 15:01:00.000000

Adds order_table.supplier_order_numbers, the numbers under which the
supplier keeps an order, as a JSON list stored in a text column (the
model's StringListType), so the order filters and the global search can
match an entry with LIKE. The server default gives every existing order an
empty list, which is what a fresh install holds, so no data step is needed.
Downgrade drops the column and the numbers stored in it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9100b6a4650a"
down_revision: str | None = "0dcb223dd17a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "order_table"
_COLUMN = "supplier_order_numbers"


def _has_column() -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(_TABLE)
    return any(column["name"] == _COLUMN for column in columns)


def upgrade() -> None:
    if _has_column():
        return
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.Text(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    if not _has_column():
        return
    # SQLite cannot drop a column in place.
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
