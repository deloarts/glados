import { webApi } from '@/core/api/webRequest'

import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

// Mirrors reorderProductionOrders.ts's path/base construction, scoped to a
// machine pool's own queue_sequence namespace instead of a single machine's;
// see the pool-scoped reorder endpoint added alongside pool-assignment
// (ReassignProductionOrderMachineRequest.machine_pool_id).
export async function reorderProductionOrdersByPool(
  poolId: number,
  orderedProductionOrderIds: number[],
): Promise<ProductionOrderResponse[]> {
  return webApi.put('/production-orders/machines/pools/{pool_id}/queue', {
    path: { pool_id: poolId },
    body: { ordered_production_order_ids: orderedProductionOrderIds },
  })
}
