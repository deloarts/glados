import { webApi } from '@/core/api/webRequest'

import type { OrderItemResponse } from '../types/ordersResponse'

/**
 * Reopens a line closed short: its quantity goes back to what it was before
 * the close and it waits for the rest again.
 */
export async function reopenOrderItem(
  orderId: number,
  orderItemId: number,
  expectedEditVersion: number,
): Promise<OrderItemResponse> {
  return webApi.post('/orders/{order_id}/items/{order_item_id}/reopen', {
    path: { order_id: orderId, order_item_id: orderItemId },
    query: { expected_edit_version: expectedEditVersion },
  })
}
