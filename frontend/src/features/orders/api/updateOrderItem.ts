import { webApi } from '@/core/api/webRequest'
import type { OrderItemUpdateRequest } from '../types/ordersRequest'
import type { OrderItemResponse } from '../types/ordersResponse'

export async function updateOrderItem(
  orderId: number,
  itemId: number,
  payload: OrderItemUpdateRequest,
): Promise<OrderItemResponse> {
  return webApi.put('/orders/{order_id}/items/{order_item_id}', {
    path: { order_id: orderId, order_item_id: itemId },
    body: payload,
  })
}
