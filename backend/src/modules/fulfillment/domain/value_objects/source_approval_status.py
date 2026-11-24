"""
Status enum for ProductionLot.source_approval_status, a real stored
column (see ProductionLot's own field docstring), not
derived at read time, so the "Needs Approval" list filter can use a cheap
SQL predicate instead of walking every lot's demand state.

It also says whether the lot needs our raw material at all. A supplier who
does the lot's first position brings the material, so such a lot has no
demand and nothing to approve: AWAITING_FIRST_STEP while the routing only
predicts it (every fabrication step of position 1 uses a method that is
required external), SUPPLIER_SOURCED once position 1 is EXTERNAL
(lot_material_rules.py).

Its writers are ApproveLotSource and RejectLotSource, CreateLot and
SwitchLotMaterialSource, which set the first value on creation or a source
switch, the backfill of UpdateProductionSettings, and the material
follow-up of the lifecycle reconciler (lot_material_followup.py), which
moves it when position 1 changes its kind. Approving, rejecting and
switching are rules of the lot intent table (APPROVE_SOURCE, REJECT_SOURCE,
SWITCH_SOURCE), which reads this status from the lot's context, so the use
cases and the actions a lot offers agree on when a decision can be taken.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class SourceApprovalStatus(StrValueEnum):
    # require_source_item_approval is off, or the source isn't a SourceItem
    NOT_REQUIRED = "not_required"
    PENDING = "pending"  # awaiting an approve/reject decision, no demand exists yet
    APPROVED = "approved"  # approved_by/date set; demand created
    # rejected_by/date/reason set; sticky until re-approved or source switched
    REJECTED = "rejected"
    # Position 1 is unassigned and its routing says a supplier does it; no demand
    AWAITING_FIRST_STEP = "awaiting_first_step"
    # Position 1 is EXTERNAL, the supplier brings the material; no demand
    SUPPLIER_SOURCED = "supplier_sourced"

    @classmethod
    def default(cls) -> "SourceApprovalStatus":
        return cls.NOT_REQUIRED


# The statuses of a lot whose material the supplier of position 1 brings.
SUPPLIER_MATERIAL_STATUSES: frozenset[SourceApprovalStatus] = frozenset(
    {SourceApprovalStatus.AWAITING_FIRST_STEP, SourceApprovalStatus.SUPPLIER_SOURCED}
)
