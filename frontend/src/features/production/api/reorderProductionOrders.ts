import { webApi } from '@/core/api/webRequest'

import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function reorderProductionOrders(
  machineId: number | null,
  orderedProductionOrderIds: number[],
): Promise<ProductionOrderResponse[]> {
  const body = { ordered_production_order_ids: orderedProductionOrderIds }
  if (machineId === null) {
    return webApi.put('/production-orders/machines/unassigned/queue', {
      body,
    })
  }
  return webApi.put('/production-orders/machines/{machine_id}/queue', {
    path: { machine_id: machineId },
    body,
  })
}
