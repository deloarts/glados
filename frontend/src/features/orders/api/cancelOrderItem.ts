import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

/**
 * Cancels a line on which nothing was delivered or lost; its demands are
 * released.
 */
export async function cancelOrderItem(
  orderId: number,
  orderItemId: number,
  expectedEditVersion: number,
): Promise<OrderItemResponse> {
  return webApi.post('/orders/{order_id}/items/{order_item_id}/cancel', {
    path: { order_id: orderId, order_item_id: orderItemId },
    query: { expected_edit_version: expectedEditVersion },
  })
}
