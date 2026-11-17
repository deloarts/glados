import { webApi } from '@/core/api/webRequest'

import type { CancelProductionOrderRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function cancelProductionOrder(
  id: number,
  payload: CancelProductionOrderRequest,
): Promise<ProductionOrderResponse> {
  return webApi.post('/production-orders/{production_order_id}/cancel', {
    path: { production_order_id: id },
    body: payload,
  })
}
