"""
Status enum for ProductionLot.source_approval_status, a real stored
column (see ProductionLot's own field docstring), not
derived at read time, so the "Needs Approval" list filter can use a cheap
SQL predicate instead of walking every lot's demand state.

Nothing derives it: its writers are ApproveLotSource and RejectLotSource,
CreateLot and SwitchLotMaterialSource, which set `not_required` or
`pending` on creation or a source switch, and the backfill of
UpdateProductionSettings. Approving, rejecting and switching are rules of
the lot intent table (APPROVE_SOURCE, REJECT_SOURCE, SWITCH_SOURCE), which
reads this status from the lot's context, so the use cases and the actions
a lot offers agree on when a decision can be taken.
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

    @classmethod
    def default(cls) -> "SourceApprovalStatus":
        return cls.NOT_REQUIRED
