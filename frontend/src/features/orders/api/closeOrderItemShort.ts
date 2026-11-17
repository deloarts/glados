import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

/**
 * Closes a line at the pieces delivered or lost on it; the supplier sends
 * nothing more for it.
 */
export async function closeOrderItemShort(
  orderId: number,
  orderItemId: number,
  expectedEditVersion: number,
): Promise<OrderItemResponse> {
  return webApi.post('/orders/{order_id}/items/{order_item_id}/close-short', {
    path: { order_id: orderId, order_item_id: orderItemId },
    query: { expected_edit_version: expectedEditVersion },
  })
}
