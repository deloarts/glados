import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { CorrectDeliveryRequest } from '../types/ordersRequest'
import type { OrderItemResponse } from '../types/ordersResponse'

/**
 * Takes accepted pieces of one delivery back with a reason, as a negative
 * delivery row naming the corrected one.
 */
export async function correctOrderItemDelivery(
  orderId: number,
  orderItemId: number,
  deliveryId: number,
  payload: CorrectDeliveryRequest,
): Promise<OrderItemResponse> {
  return sendIdempotent((config) =>
    webApi.post('/orders/{order_id}/items/{order_item_id}/deliveries/{delivery_id}/correct', {
      path: { order_id: orderId, order_item_id: orderItemId, delivery_id: deliveryId },
      body: payload,
      config,
    }),
  )
}
