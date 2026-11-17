import type { AutoPlanSkipReason } from '../types/scheduleBoardResponse'

// An explicit array, unlike a Record, allows a fallback for unknown reasons.
const KNOWN_SKIP_REASONS: AutoPlanSkipReason[] = [
  'waiting_on_material',
  'no_eligible_machine',
  'no_eligible_pool',
  'no_eligible_pool_member',
  'machine_down',
  'changed_while_planning',
]

function isKnownSkipReason(reason: string): reason is AutoPlanSkipReason {
  return (KNOWN_SKIP_REASONS as string[]).includes(reason)
}

// Accepts any string, since the backend may add a reason first.
export function skipReasonLabelKey(reason: string): string {
  return isKnownSkipReason(reason)
    ? `productionSchedule.autoPlan.skippedOrders.reasons.${reason}`
    : 'productionSchedule.autoPlan.skippedOrders.reasons.unknown'
}

export function skipReasonTooltipKey(reason: string): string {
  return `${skipReasonLabelKey(reason)}Tooltip`
}
