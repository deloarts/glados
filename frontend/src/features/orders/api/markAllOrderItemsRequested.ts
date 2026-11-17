import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

export async function markAllOrderItemsRequested(orderId: number): Promise<OrderItemResponse[]> {
  return webApi.put('/orders/{order_id}/mark-items-requested', { path: { order_id: orderId } })
}
