import type { ScheduleConflict } from '../types/productionOrdersResponse'

export const conflictSeverity: Record<ScheduleConflict, string> = {
  no_machine_assigned: 'secondary',
  capability_mismatch: 'danger',
  uncategorized_step: 'warn',
  position_not_fully_queued: 'warn',
  waiting_on_predecessor: 'info',
  // Harder blocker than waiting_on_predecessor: this is a sequence-1 order
  // whose raw material hasn't even arrived yet (no demand, unallocated, or
  // undelivered). Nothing to do but wait on receiving, so it's flagged a
  // level above the plain "info" a mid-chain predecessor wait gets.
  waiting_on_material: 'warn',
  estimate_from_time_budget: 'secondary',
  missing_time_estimate: 'warn',
  past_target_date: 'danger',
  external_date_before_predecessor: 'warn',
  // The order's own machine is unavailable right now, not just a soft
  // scheduling nudge, so it gets the hardest severity level, same as
  // past_target_date.
  machine_down: 'danger',
  // The machine has no working time at all, so the order has no dates.
  no_working_time: 'danger',
  // A pinned or frozen window that the order before it runs into.
  window_overlap: 'warn',
  // A pinned or frozen window that starts before its pieces can be there.
  window_before_predecessor: 'warn',
  // A step queued ahead of its own predecessor: undated until reordered.
  chain_cycle: 'danger',
}

export function conflictLabelKey(conflict: ScheduleConflict): string {
  return `productionQueue.conflicts.${conflict}`
}

export function conflictTooltipKey(conflict: ScheduleConflict): string {
  return `productionQueue.conflicts.${conflict}Tooltip`
}
