import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { WebRequestConfig } from '@/core/api/webRequest'
import type { OrderFilterParams } from '../types/ordersRequest'
import type { OrderResponse } from '../types/ordersResponse'

export async function getOrders(
  params?: OrderFilterParams,
  config?: WebRequestConfig,
): Promise<PageResponse<OrderResponse>> {
  return webApi.get('/orders/', { query: params, config })
}
