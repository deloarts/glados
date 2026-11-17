import { webApi } from '@/core/api/webRequest'

import type { OrderResponse } from '../types/ordersResponse'

export async function requestOrder(id: number): Promise<OrderResponse> {
  return webApi.put('/orders/{order_id}/request', {
    path: { order_id: id },
  })
}
