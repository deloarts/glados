import { webApi } from '@/core/api/webRequest'

import type { MergeProductionOrdersRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function mergeProductionOrders(
  payload: MergeProductionOrdersRequest,
): Promise<ProductionOrderResponse> {
  return webApi.post('/production-orders/merge', {
    body: payload,
  })
}
