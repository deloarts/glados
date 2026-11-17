import { webApi } from '@/core/api/webRequest'

import type { SplitProductionOrderRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function splitProductionOrder(
  id: number,
  payload: SplitProductionOrderRequest,
): Promise<ProductionOrderResponse[]> {
  return webApi.post('/production-orders/{production_order_id}/split', {
    path: { production_order_id: id },
    body: payload,
  })
}
