"""add external work latest dates

Revision ID: 9ee3cd40f95e
Revises: 9100b6a4650a
Create Date: 2026-11-23 15:54:00.000000

Adds lot_position_table.latest_pickup_date, the latest day a position of
external work can leave for the supplier without making its lot miss the
target date, lot_position_table.latest_delivery_date, the day it is back at
the latest when it leaves then, and
admin_production_settings.external_safety_margin_days, the days kept free
before the target date when those days are counted back. The schedule walk
writes both dates, so existing positions start NULL, as on a fresh install,
and the next walk fills them. The server default gives the settings row the
default margin of 2 days, so no data step is needed. Downgrade drops the
three columns and the values stored in them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ee3cd40f95e"
down_revision: str | None = "9100b6a4650a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POSITION_TABLE = "lot_position_table"
_LATEST_PICKUP = "latest_pickup_date"
_LATEST_DELIVERY = "latest_delivery_date"
_SETTINGS_TABLE = "admin_production_settings"
_SAFETY_MARGIN = "external_safety_margin_days"


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(existing["name"] == column for existing in columns)


def upgrade() -> None:
    for column in (_LATEST_PICKUP, _LATEST_DELIVERY):
        if not _has_column(_POSITION_TABLE, column):
            op.add_column(_POSITION_TABLE, sa.Column(column, sa.Date(), nullable=True))
    if not _has_column(_SETTINGS_TABLE, _SAFETY_MARGIN):
        op.add_column(
            _SETTINGS_TABLE,
            sa.Column(_SAFETY_MARGIN, sa.Integer(), server_default="2", nullable=False),
        )


def downgrade() -> None:
    # SQLite cannot drop a column in place.
    if _has_column(_SETTINGS_TABLE, _SAFETY_MARGIN):
        with op.batch_alter_table(_SETTINGS_TABLE) as batch_op:
            batch_op.drop_column(_SAFETY_MARGIN)
    for column in (_LATEST_DELIVERY, _LATEST_PICKUP):
        if _has_column(_POSITION_TABLE, column):
            with op.batch_alter_table(_POSITION_TABLE) as batch_op:
                batch_op.drop_column(column)
