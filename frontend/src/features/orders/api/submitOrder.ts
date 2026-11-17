import { webApi } from '@/core/api/webRequest'

import type { OrderResponse } from '../types/ordersResponse'

export async function submitOrder(id: number): Promise<OrderResponse> {
  return webApi.put('/orders/{order_id}/submit', {
    path: { order_id: id },
  })
}
