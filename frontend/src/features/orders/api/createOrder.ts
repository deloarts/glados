import { webApi } from '@/core/api/webRequest'

import type { OrderCreateRequest } from '../types/ordersRequest'
import type { OrderResponse } from '../types/ordersResponse'

export async function createOrder(payload: OrderCreateRequest): Promise<OrderResponse> {
  return webApi.post('/orders/', { body: payload })
}
