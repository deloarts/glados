import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

export async function markAllOrderItemsOrdered(orderId: number): Promise<OrderItemResponse[]> {
  return webApi.put('/orders/{order_id}/mark-items-ordered', { path: { order_id: orderId } })
}
