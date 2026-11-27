"""add booking details and assessment history

Revision ID: 1d9522656391
Revises: 4788f43a8638
Create Date: 2026-11-27 09:22:52.000000

Records what the bookings of a production order left out, so its work time
can later be read from the bookings alone.

On production_order_interruption_table: resumed_operator_id, the operator
who went on with the work when the order's own start resumed it; ended_by,
which tells a resume from a cancel or a cut that closes the row without any
work following it; and pause_cause, the cause an operator picked for a
manual pause. On production_order_table: first_started_operator_id, the
operator of the first start, which started_operator_id overwrites on every
resume. All four are nullable and stay empty on existing rows, since the
bookings so far do not say what they would hold; there is no backfill.

On manufacturing_assessment_table: actual_minutes_per_piece becomes a float,
because whole minutes distort short cycles, and every stored whole number
converts as it is. superseded_at marks an assessment that a later one of the
same order replaced after a reversed completion, and the unique index on
production_order_id becomes a partial one over the rows not superseded, so
an order still has at most one active assessment.

Downgrade deletes the superseded assessments, since the full unique index
allows one row per order, rounds the minutes to whole numbers, restores the
integer column and the full unique index, and drops the new columns with
the values stored in them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1d9522656391"
down_revision: str | None = "4788f43a8638"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTERRUPTION_TABLE = "production_order_interruption_table"
_ORDER_TABLE = "production_order_table"
_ASSESSMENT_TABLE = "manufacturing_assessment_table"

_RESUMED_OPERATOR = "resumed_operator_id"
_RESUMED_OPERATOR_FK = "fk_production_order_interruption_resumed_operator_id"
_RESUMED_OPERATOR_INDEX = "ix_production_order_interruption_table_resumed_operator_id"

_FIRST_OPERATOR = "first_started_operator_id"
_FIRST_OPERATOR_FK = "fk_production_order_first_started_operator_id"
_FIRST_OPERATOR_INDEX = "ix_production_order_table_first_started_operator_id"

_MINUTES = "actual_minutes_per_piece"
_SUPERSEDED = "superseded_at"
_ASSESSMENT_ORDER_INDEX = "ix_manufacturing_assessment_table_production_order_id"


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(existing["name"] == column for existing in columns)


def _has_index(table: str, name: str) -> bool:
    indexes = sa.inspect(op.get_bind()).get_indexes(table)
    return any(existing["name"] == name for existing in indexes)


def _has_foreign_key(table: str, name: str) -> bool:
    keys = sa.inspect(op.get_bind()).get_foreign_keys(table)
    return any(existing["name"] == name for existing in keys)


def _add_user_column(table: str, column: str, fk_name: str, index_name: str) -> None:
    """Adds a nullable user reference with its named foreign key and index.
    SQLite cannot add a constraint in place, hence the batch."""
    if not _has_column(table, column):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column(column, sa.Integer(), nullable=True))
            batch_op.create_foreign_key(fk_name, "user_table", [column], ["id"])
    if not _has_index(table, index_name):
        op.create_index(index_name, table, [column], unique=False)


def _drop_user_column(table: str, column: str, fk_name: str, index_name: str) -> None:
    if _has_index(table, index_name):
        op.drop_index(index_name, table_name=table)
    if _has_column(table, column):
        with op.batch_alter_table(table) as batch_op:
            if _has_foreign_key(table, fk_name):
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.drop_column(column)


def upgrade() -> None:
    _add_user_column(
        _INTERRUPTION_TABLE, _RESUMED_OPERATOR, _RESUMED_OPERATOR_FK, _RESUMED_OPERATOR_INDEX
    )
    for column in ("ended_by", "pause_cause"):
        if not _has_column(_INTERRUPTION_TABLE, column):
            op.add_column(_INTERRUPTION_TABLE, sa.Column(column, sa.String(), nullable=True))
    _add_user_column(_ORDER_TABLE, _FIRST_OPERATOR, _FIRST_OPERATOR_FK, _FIRST_OPERATOR_INDEX)

    if not _has_column(_ASSESSMENT_TABLE, _SUPERSEDED):
        op.add_column(
            _ASSESSMENT_TABLE,
            sa.Column(_SUPERSEDED, sa.DateTime(timezone=True), nullable=True),
        )
    # SQLite cannot change a column type in place.
    with op.batch_alter_table(_ASSESSMENT_TABLE) as batch_op:
        batch_op.alter_column(
            _MINUTES,
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
        )
    if _has_index(_ASSESSMENT_TABLE, _ASSESSMENT_ORDER_INDEX):
        op.drop_index(_ASSESSMENT_ORDER_INDEX, table_name=_ASSESSMENT_TABLE)
    op.create_index(
        _ASSESSMENT_ORDER_INDEX,
        _ASSESSMENT_TABLE,
        ["production_order_id"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
        sqlite_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    if _has_index(_ASSESSMENT_TABLE, _ASSESSMENT_ORDER_INDEX):
        op.drop_index(_ASSESSMENT_ORDER_INDEX, table_name=_ASSESSMENT_TABLE)
    if _has_column(_ASSESSMENT_TABLE, _SUPERSEDED):
        # The full unique index below allows one row per order, which only
        # the active assessment keeps.
        op.execute(sa.text(f"DELETE FROM {_ASSESSMENT_TABLE} WHERE {_SUPERSEDED} IS NOT NULL"))
    op.execute(sa.text(f"UPDATE {_ASSESSMENT_TABLE} SET {_MINUTES} = ROUND({_MINUTES})"))
    with op.batch_alter_table(_ASSESSMENT_TABLE) as batch_op:
        batch_op.alter_column(
            _MINUTES,
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using=f"ROUND({_MINUTES})::integer",
        )
        if _has_column(_ASSESSMENT_TABLE, _SUPERSEDED):
            batch_op.drop_column(_SUPERSEDED)
    op.create_index(
        _ASSESSMENT_ORDER_INDEX, _ASSESSMENT_TABLE, ["production_order_id"], unique=True
    )

    _drop_user_column(_ORDER_TABLE, _FIRST_OPERATOR, _FIRST_OPERATOR_FK, _FIRST_OPERATOR_INDEX)
    for column in ("pause_cause", "ended_by"):
        if _has_column(_INTERRUPTION_TABLE, column):
            with op.batch_alter_table(_INTERRUPTION_TABLE) as batch_op:
                batch_op.drop_column(column)
    _drop_user_column(
        _INTERRUPTION_TABLE, _RESUMED_OPERATOR, _RESUMED_OPERATOR_FK, _RESUMED_OPERATOR_INDEX
    )
