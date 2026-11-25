"""add handoff and wait after minutes

Revision ID: 4788f43a8638
Revises: aeb017243e8c
Create Date: 2026-11-25 12:59:00.000000

Adds admin_production_settings.internal_handoff_minutes, the buffer the
schedule walk adds between two in-house positions of a lot, while
response_time_days stays the buffer after an arrival. The server default of
0 gives the existing settings row the value a fresh install has, so no data
step is needed.

Adds wait_after_minutes to fabrication_method_table and
inspection_method_table, the clock minutes the pieces wait after a step of
that method before the next one may start, such as curing or a lab result.
Both are nullable, and an existing method waits nothing.

Downgrade drops the three columns and the values stored in them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4788f43a8638"
down_revision: str | None = "aeb017243e8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETTINGS_TABLE = "admin_production_settings"
_HANDOFF_COLUMN = "internal_handoff_minutes"
_METHOD_TABLES = ("fabrication_method_table", "inspection_method_table")
_WAIT_COLUMN = "wait_after_minutes"


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(existing["name"] == column for existing in columns)


def upgrade() -> None:
    if not _has_column(_SETTINGS_TABLE, _HANDOFF_COLUMN):
        op.add_column(
            _SETTINGS_TABLE,
            sa.Column(_HANDOFF_COLUMN, sa.Integer(), server_default="0", nullable=False),
        )
    for table in _METHOD_TABLES:
        if not _has_column(table, _WAIT_COLUMN):
            op.add_column(table, sa.Column(_WAIT_COLUMN, sa.Integer(), nullable=True))


def downgrade() -> None:
    # SQLite cannot drop a column in place.
    for table in _METHOD_TABLES:
        if _has_column(table, _WAIT_COLUMN):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column(_WAIT_COLUMN)
    if _has_column(_SETTINGS_TABLE, _HANDOFF_COLUMN):
        with op.batch_alter_table(_SETTINGS_TABLE) as batch_op:
            batch_op.drop_column(_HANDOFF_COLUMN)
