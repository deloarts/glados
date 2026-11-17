import { webApi } from '@/core/api/webRequest'

import type { OrderUpdateRequest } from '../types/ordersRequest'
import type { OrderResponse } from '../types/ordersResponse'

export async function updateOrder(id: number, payload: OrderUpdateRequest): Promise<OrderResponse> {
  return webApi.put('/orders/{order_id}', {
    path: { order_id: id },
    body: payload,
  })
}
