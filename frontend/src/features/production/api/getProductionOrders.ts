import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { ProductionOrderFilterParams } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function getProductionOrders(
  params?: ProductionOrderFilterParams,
): Promise<PageResponse<ProductionOrderResponse>> {
  return webApi.get('/production-orders/', {
    query: params,
  })
}
