"""
Reasons AutoPlan reports a candidate as skipped (AutoPlanResult.skipped):
sibling of ScheduleConflictReason, same shape, different concern:
ScheduleConflictReason badges an order's already-persisted state,
AutoPlanSkipReason explains a candidate a single run's placement loop
declined to place, or placed in a queue that changed before the plan was
written. Such a candidate keeps its machine_id and machine_pool_id; the
write phase gives it its queue place back.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class AutoPlanSkipReason(StrValueEnum):
    # Same gate scheduling.is_unplannable_for_missing_material
    # applies to the forward walk itself: a sequence-1 INTERNAL/MIXED
    # candidate whose raw material has neither arrived nor has a delivery
    # forecast. Checked before any machine/pool resolution is even
    # trialed; there is no eligible-machine/eligible-pool concept that
    # would help here, the walk would return no dates on every one of
    # them regardless (advance_machine_queue's own new branch).
    WAITING_ON_MATERIAL = "waiting_on_material"
    # 'machines' level (also the pool-resolution rule at 'machines' level
    # for a pool-assigned-unresolved order): resolve_eligible_machine_ids
    # returned no candidate machine at all: no capable machine in scope,
    # or (assign_machines=False) the order isn't already on one.
    NO_ELIGIBLE_MACHINE = "no_eligible_machine"
    # 'pools' level: resolve_eligible_pool_ids returned no pool whose
    # derived capability (the intersection of its members' fabrication
    # methods) covers this candidate's required methods.
    NO_ELIGIBLE_POOL = "no_eligible_pool"
    # 'pools' level: at least one pool WAS capability-eligible
    # (NO_ELIGIBLE_POOL above did not apply), but resolve_pool_for_
    # candidate still returned None; none of those pools had a single
    # member present in this run's own machine scope/calendars (e.g. every
    # member was excluded by AutoPlanCommand.machine_ids), so there was no
    # timeable member to trial a concrete slot against. Distinct from
    # NO_ELIGIBLE_POOL: that's a capability gap, this is a scope gap.
    NO_ELIGIBLE_POOL_MEMBER = "no_eligible_pool_member"
    # Every machine (or every member of every capability-eligible pool)
    # this candidate could otherwise have gone to has an open downtime at
    # run time, distinct from NO_ELIGIBLE_MACHINE/NO_ELIGIBLE_POOL_MEMBER:
    # those mean no machine ever qualified, this means one did and was
    # excluded solely for being down right now.
    MACHINE_DOWN = "machine_down"
    # Placed by the run, but the queue it came from or went to changed
    # between the run's read and its write: an order there was started,
    # pinned, moved, added or ended meanwhile. The placement is not written,
    # and a run on the current queues places it again.
    CHANGED_WHILE_PLANNING = "changed_while_planning"
