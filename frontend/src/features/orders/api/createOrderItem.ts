import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { OrderItemCreateRequest } from '../types/ordersRequest'
import type { OrderItemResponse } from '../types/ordersResponse'

export async function createOrderItem(
  orderId: number,
  payload: Omit<OrderItemCreateRequest, 'order_id'>,
): Promise<OrderItemResponse> {
  return sendIdempotent((config) =>
    webApi.post('/orders/{order_id}/items', {
      path: { order_id: orderId },
      body: {
        ...payload,
        order_id: orderId,
      },
      config,
    }),
  )
}
