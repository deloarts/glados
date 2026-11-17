import { webApi } from '@/core/api/webRequest'

import type { PauseProductionOrderRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function pauseProductionOrder(
  id: number,
  payload: PauseProductionOrderRequest = {},
): Promise<ProductionOrderResponse> {
  return webApi.post('/production-orders/{production_order_id}/pause', {
    path: { production_order_id: id },
    body: payload,
  })
}
