import { webApi } from '@/core/api/webRequest'
import type { OrderItemResponse } from '../types/ordersResponse'

export async function moveOrderItem(
  orderId: number,
  itemId: number,
  targetOrderId: number,
): Promise<OrderItemResponse> {
  return webApi.put('/orders/{order_id}/items/{order_item_id}/move', {
    path: { order_id: orderId, order_item_id: itemId },
    body: {
      target_order_id: targetOrderId,
    },
  })
}
