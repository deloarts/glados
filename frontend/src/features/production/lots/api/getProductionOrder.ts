import { webApi } from '@/core/api/webRequest'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

export async function getProductionOrder(id: number): Promise<ProductionOrderResponse> {
  return webApi.get('/production-orders/{production_order_id}', {
    path: { production_order_id: id },
  })
}
