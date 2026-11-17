import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

export async function markOrderItemReadyForPickup(
  orderId: number,
  orderItemId: number,
): Promise<OrderItemResponse> {
  return webApi.put('/orders/{order_id}/items/{order_item_id}/mark-ready-for-pickup', {
    path: { order_id: orderId, order_item_id: orderItemId },
  })
}
