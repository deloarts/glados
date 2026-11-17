import type { ProductionOrderResponse } from '../types/productionOrdersResponse'
import type { StepRole } from '../types/productionLotsResponse'

export type BoardColumnKind = 'unassigned' | 'manual' | 'inspection' | 'machine' | 'pool'

/** Satisfied by both LotStepResponse and LotSummaryStepResponse. */
export interface RoutingStep {
  role: StepRole
  fabrication_method_requires_machine: boolean
}

export function poolColumnKey(poolId: number): string {
  return `pool-${poolId}`
}

// A position without resolved steps counts as unassigned, so a blocked
// order never hides in the informational column.
export function isManualOrder(steps: RoutingStep[]): boolean {
  return steps.length > 0 && steps.every((s) => !s.fabrication_method_requires_machine)
}

// Inspection steps also need no machine, so callers must check this before
// isManualOrder.
export function isInspectionOrder(steps: RoutingStep[]): boolean {
  return steps.some((s) => s.role === 'inspection')
}

// Manual and inspection columns are machine-less by nature, so they are
// read-only: no drag and no missing-machine conflict.
export function isStaticColumn(kind: BoardColumnKind): boolean {
  return kind === 'manual' || kind === 'inspection'
}

// A resolved machine wins, then an unresolved pool, then the manual,
// inspection or unassigned column. Display grouping only.
export function orderColumnKey(
  order: Pick<ProductionOrderResponse, 'machine_id' | 'machine_pool_id'>,
  steps: RoutingStep[],
): string {
  if (order.machine_id !== null) return String(order.machine_id)
  if (order.machine_pool_id != null) return poolColumnKey(order.machine_pool_id)
  if (isInspectionOrder(steps)) return 'inspection'
  return isManualOrder(steps) ? 'manual' : 'unassigned'
}
