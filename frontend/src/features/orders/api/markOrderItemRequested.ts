import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

export async function markOrderItemRequested(
  orderId: number,
  orderItemId: number,
): Promise<OrderItemResponse> {
  return webApi.put('/orders/{order_id}/items/{order_item_id}/mark-requested', {
    path: { order_id: orderId, order_item_id: orderItemId },
  })
}
