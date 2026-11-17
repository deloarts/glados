import { webApi } from '@/core/api/webRequest'

import type { ReverseCompletionRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function reverseProductionOrderCompletion(
  productionOrderId: number,
  completionId: number,
  payload: ReverseCompletionRequest,
): Promise<ProductionOrderResponse> {
  return webApi.post('/production-orders/{production_order_id}/completions/{completion_id}/reverse', {
    path: { production_order_id: productionOrderId, completion_id: completionId },
    body: payload,
  })
}
