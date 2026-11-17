import { webApi } from '@/core/api/webRequest'

import type { OrderResponse } from '../types/ordersResponse'

export async function getOrder(id: number): Promise<OrderResponse> {
  return webApi.get('/orders/{order_id}', { path: { order_id: id } })
}
