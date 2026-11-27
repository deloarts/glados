"""add planning settings and plan baseline

Revision ID: 32f4e11f40ab
Revises: 1d9522656391
Create Date: 2026-11-27 12:17:08.000000

Adds admin_planning_settings, the singleton of the planning features that
work next to the scheduler: commit_horizon_working_days (the working days
the nightly baseline records), plan_retention_days (how long recorded plans
are kept) and booking_quality_since (from when the booking quality view
counts bookings). The row is created by InitDatabase on the next start like
every other settings singleton, and its booking_quality_since defaults to
that moment, so bookings from before the upgrade are not judged.

Adds production_plan_table, one row per recorded plan with a partial unique
index that allows one baseline per day, and its rows:
production_plan_entry_table, one per order inside the committed horizon, and
production_plan_lot_table, one per open lot. Both copy the numbers that
identify their order and lot, and their references to orders, positions and
lots are set to null when those are deleted. Deleting a plan deletes its
rows.

Downgrade drops the four tables and the plans recorded in them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32f4e11f40ab"
down_revision: str | None = "1d9522656391"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETTINGS = "admin_planning_settings"
_PLAN = "production_plan_table"
_ENTRY = "production_plan_entry_table"
_LOT = "production_plan_lot_table"


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _public_id() -> sa.Column[object]:
    return sa.Column("public_id", sa.Uuid(), nullable=False)


def _index_public_id(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_public_id"), table, ["public_id"], unique=True)


def upgrade() -> None:
    if not _has_table(_SETTINGS):
        op.create_table(
            _SETTINGS,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "commit_horizon_working_days", sa.Integer(), server_default="5", nullable=False
            ),
            sa.Column("plan_retention_days", sa.Integer(), server_default="400", nullable=False),
            sa.Column(
                "booking_quality_since",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            _public_id(),
            sa.PrimaryKeyConstraint("id"),
        )
        _index_public_id(_SETTINGS)

    if not _has_table(_PLAN):
        op.create_table(
            _PLAN,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created", sa.DateTime(timezone=True), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("scheduler_mode", sa.String(), nullable=False),
            sa.Column("engine", sa.String(), nullable=False),
            sa.Column("engine_version", sa.String(), nullable=False),
            sa.Column("plan_day", sa.Date(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            _public_id(),
            sa.PrimaryKeyConstraint("id"),
        )
        _index_public_id(_PLAN)
        op.create_index("ix_production_plan_table_plan_day", _PLAN, ["plan_day"], unique=False)
        op.create_index(
            "uq_production_plan_baseline_day",
            _PLAN,
            ["plan_day"],
            unique=True,
            postgresql_where=sa.text("kind = 'baseline'"),
            sqlite_where=sa.text("kind = 'baseline'"),
        )

    if not _has_table(_ENTRY):
        op.create_table(
            _ENTRY,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("production_order_id", sa.Integer(), nullable=True),
            sa.Column("lot_position_id", sa.Integer(), nullable=True),
            sa.Column("lot_id", sa.Integer(), nullable=False),
            sa.Column("position_sequence", sa.Integer(), nullable=False),
            sa.Column("production_order_number", sa.String(), nullable=False),
            sa.Column("machine_id", sa.Integer(), nullable=True),
            sa.Column("machine_pool_id", sa.Integer(), nullable=True),
            sa.Column("queue_sequence", sa.Integer(), nullable=False),
            sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            _public_id(),
            sa.ForeignKeyConstraint(
                ["plan_id"],
                [f"{_PLAN}.id"],
                name="fk_production_plan_entry_plan_id",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["production_order_id"],
                ["production_order_table.id"],
                name="fk_production_plan_entry_production_order_id",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["lot_position_id"],
                ["lot_position_table.id"],
                name="fk_production_plan_entry_lot_position_id",
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        _index_public_id(_ENTRY)
        for column in ("plan_id", "production_order_id", "lot_position_id"):
            op.create_index(op.f(f"ix_{_ENTRY}_{column}"), _ENTRY, [column], unique=False)

    if not _has_table(_LOT):
        op.create_table(
            _LOT,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("lot_id", sa.Integer(), nullable=True),
            sa.Column("lot_number", sa.String(), nullable=False),
            sa.Column("target_date", sa.Date(), nullable=True),
            sa.Column("planned_finish", sa.DateTime(timezone=True), nullable=True),
            _public_id(),
            sa.ForeignKeyConstraint(
                ["plan_id"],
                [f"{_PLAN}.id"],
                name="fk_production_plan_lot_plan_id",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["lot_id"],
                ["production_lot_table.id"],
                name="fk_production_plan_lot_lot_id",
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        _index_public_id(_LOT)
        for column in ("plan_id", "lot_id"):
            op.create_index(op.f(f"ix_{_LOT}_{column}"), _LOT, [column], unique=False)


def downgrade() -> None:
    # The row tables first, since they reference the plans.
    for table in (_LOT, _ENTRY, _PLAN, _SETTINGS):
        if _has_table(table):
            op.drop_table(table)
