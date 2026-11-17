import { webApi } from '@/core/api/webRequest'

import type { OrderResponse } from '../types/ordersResponse'

/** `expectedEditVersion` is the order's edit version the user saw; an order
 * changed since answers 409. */
export async function cancelOrder(id: number, expectedEditVersion: number): Promise<OrderResponse> {
  return webApi.put('/orders/{order_id}/cancel', {
    path: { order_id: id },
    query: { expected_edit_version: expectedEditVersion },
  })
}
