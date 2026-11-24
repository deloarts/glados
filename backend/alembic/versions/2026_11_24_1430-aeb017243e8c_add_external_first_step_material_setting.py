"""add external first step material setting

Revision ID: aeb017243e8c
Revises: 9ee3cd40f95e
Create Date: 2026-11-24 14:30:00.000000

Adds admin_production_settings.external_first_step_needs_no_material. While
it is on, a lot whose first position a supplier does gets no raw material
demand and needs no source approval, because the supplier brings the
material. The server default turns it on for the existing settings row, as
on a fresh install, so no data step is needed; existing lots keep the state
they have. Downgrade drops the column and the value stored in it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aeb017243e8c"
down_revision: str | None = "9ee3cd40f95e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETTINGS_TABLE = "admin_production_settings"
_COLUMN = "external_first_step_needs_no_material"


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(existing["name"] == column for existing in columns)


def upgrade() -> None:
    if not _has_column(_SETTINGS_TABLE, _COLUMN):
        op.add_column(
            _SETTINGS_TABLE,
            sa.Column(_COLUMN, sa.Boolean(), server_default="true", nullable=False),
        )


def downgrade() -> None:
    # SQLite cannot drop a column in place.
    if _has_column(_SETTINGS_TABLE, _COLUMN):
        with op.batch_alter_table(_SETTINGS_TABLE) as batch_op:
            batch_op.drop_column(_COLUMN)
