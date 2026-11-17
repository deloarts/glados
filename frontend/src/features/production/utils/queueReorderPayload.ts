import { isProductionOrderLocked } from './productionOrderStatus'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

/**
 * Builds the reorder payload for one queue column. The endpoint renumbers
 * only the ids it receives, so the hidden future orders are appended after
 * the visible ones in their existing order. visibleOrders must already be in
 * board order. Pinned and running orders are dropped, since the backend
 * rejects them.
 */
type LockableOrder = Pick<ProductionOrderResponse, 'id' | 'pinned' | 'status'>

export function fullQueueIdsForColumn(
  visibleOrders: LockableOrder[],
  futureOrders: LockableOrder[],
): number[] {
  const visibleIds = new Set(visibleOrders.map((o) => o.id))
  const orderedIds = visibleOrders.filter((o) => !isProductionOrderLocked(o)).map((o) => o.id)

  const futureIds = futureOrders
    .filter((o) => (o.status === 'queued' || o.status === 'paused') && !isProductionOrderLocked(o))
    .filter((o) => !visibleIds.has(o.id))
    .map((o) => o.id)

  return [...orderedIds, ...futureIds]
}
