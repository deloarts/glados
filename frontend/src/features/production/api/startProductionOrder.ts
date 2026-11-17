import { webApi } from '@/core/api/webRequest'

import type { StartProductionOrderRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function startProductionOrder(
  id: number,
  payload: StartProductionOrderRequest = {},
): Promise<ProductionOrderResponse> {
  return webApi.post('/production-orders/{production_order_id}/start', {
    path: { production_order_id: id },
    body: payload,
  })
}
