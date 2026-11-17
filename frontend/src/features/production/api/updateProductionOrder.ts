import { webApi } from '@/core/api/webRequest'

import type { UpdateProductionOrderRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function updateProductionOrder(
  id: number,
  payload: UpdateProductionOrderRequest,
): Promise<ProductionOrderResponse> {
  return webApi.patch('/production-orders/{production_order_id}', {
    path: { production_order_id: id },
    body: payload,
  })
}
