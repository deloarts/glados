import { hasAction, type HasActions, type LifecycleAction } from './lifecycleActions'

// Canonical status list + severity map for demand-status badges. Bought,
// made and source items all track the same order-fulfillment lifecycle, so
// the same status word should render as the same colour everywhere. The
// same principle lotPositionStatusSeverityFor documents in
// production/utils/lotStatus.ts for lot positions.
export const DEMAND_STATUSES = ['open', 'allocated', 'ordered', 'fulfilled', 'canceled'] as const

export type DemandStatusValue = (typeof DEMAND_STATUSES)[number]

export const DEMAND_STATUS_SEVERITY: Record<DemandStatusValue, string> = {
  open: 'info',
  allocated: 'warn',
  ordered: 'help',
  fulfilled: 'success',
  canceled: 'secondary',
}

// The only statuses a user sets on a demand; open, allocated and ordered
// follow from the demand's allocations and cannot be set.
export const MANUAL_DEMAND_STATUSES = ['fulfilled', 'canceled'] as const

export type ManualDemandStatus = (typeof MANUAL_DEMAND_STATUSES)[number]

/**
 * Whether the demand has ended, fulfilled or canceled. An ended demand asks
 * for nothing more, so a rest it never got allocated is no shortfall.
 */
export function isEndedDemandStatus(status: string): boolean {
  return (MANUAL_DEMAND_STATUSES as readonly string[]).includes(status)
}

/** The lifecycle action a manual status stands for. */
export function manualStatusAction(status: ManualDemandStatus): LifecycleAction {
  return status === 'canceled' ? 'cancel' : 'fulfil'
}

/**
 * The manual statuses the demand offers now, from its actions: a fulfilled
 * or canceled demand offers none.
 */
export function offeredManualStatuses(demand: HasActions): ManualDemandStatus[] {
  return MANUAL_DEMAND_STATUSES.filter((status) => hasAction(demand, manualStatusAction(status)))
}
