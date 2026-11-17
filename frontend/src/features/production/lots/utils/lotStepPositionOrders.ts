// Resolves which production order a lot step's position is edited against.
// A production order covers a whole position, so the step list's Machine,
// Planned Date and Complete columns all work on the position's order, and
// only when that order is unambiguous.
import type {
  LotPositionProductionOrderSummary,
  LotPositionResponse,
} from '../../types/productionLotsResponse'

// A position split across several active orders has no single order to show
// or edit, so callers fall back to a read-only summary.
export function activeOrderFor(
  position: LotPositionResponse | undefined,
): LotPositionProductionOrderSummary | null {
  if (!position || (position.kind !== 'internal' && position.kind !== 'mixed')) return null
  const active = (position.production_orders ?? []).filter((o) => o.status !== 'canceled')
  return active.length === 1 ? active[0]! : null
}

// Reassignment targets one order at a time and only while it is still
// queued or paused, matching ReassignProductionOrderMachine.
export function reassignableOrder(
  position: LotPositionResponse | undefined,
): LotPositionProductionOrderSummary | null {
  const order = activeOrderFor(position)
  if (!order) return null
  return order.status === 'queued' || order.status === 'paused' ? order : null
}

// The machine wins when machine_id is set, even if the order still remembers
// the pool it was resolved from; the cell shows that provenance separately.
export function targetKeyFor(order: LotPositionProductionOrderSummary): string | null {
  if (order.machine_id) return `machine:${order.machine_id}`
  if (order.machine_pool_id) return `pool:${order.machine_pool_id}`
  return null
}
