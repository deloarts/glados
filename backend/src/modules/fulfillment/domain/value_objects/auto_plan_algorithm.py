"""
Named, user-facing scheduling behaviors for AutoPlan. Each member is a
combination of a candidate-ordering rule and a machine-selection rule;
see the scheduling package's OrderingStrategy/SelectionStrategy (internal,
never serialized over the API) and resolve_algorithm_strategies, which
maps one of these onto that (ordering, selection) pair.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class AutoPlanAlgorithm(StrValueEnum):
    """One user-selectable auto-plan behavior."""

    # Priority+EDD ordering, earliest-finish selection, today's only
    # behavior, kept as the default.
    URGENT_FIRST = "urgent_first"
    # EDD-only ordering (ignores urgency tags), earliest-finish selection.
    # Minimizes worst-case lateness across all candidates.
    STRICT_DEADLINE = "strict_deadline"
    # No reprioritization at all, creation order only, earliest-finish
    # selection. Fully predictable, a neutral baseline.
    FAIR_QUEUE = "fair_queue"
    # Same Priority+EDD ordering as URGENT_FIRST, but least-loaded-machine
    # selection instead of earliest-finish, to spread work evenly.
    BALANCED_LOAD = "balanced_load"
    # (due_date - now) / remaining_duration, lower = more urgent,
    # earliest-finish selection. Adapts automatically as time passes; can
    # behave oddly once a due date is already in the past.
    CRITICAL_RATIO = "critical_ratio"
    # Shortest jobs first regardless of urgency/due date, earliest-finish
    # selection. Maximizes throughput; can starve long jobs indefinitely.
    SHORTEST_PROCESSING_TIME = "shortest_processing_time"

    @classmethod
    def default(cls) -> "AutoPlanAlgorithm":
        return cls.URGENT_FIRST
