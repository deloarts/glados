import { sendIdempotent } from '@/core/api/idempotency'
import { webApi, type QueryOf } from '@/core/api/webRequest'

import type { DeliveryRejectionRequest } from '../types/ordersRequest'
import type { OrderItemResponse } from '../types/ordersResponse'

type DeliverQuery = QueryOf<'/bought-items-allocations/order-item/{order_item_id}/deliver', 'put'>

export async function deliverOrderItem(
  orderItemId: number,
  quantity?: number,
  storagePlace?: string,
  rejection?: DeliveryRejectionRequest,
): Promise<OrderItemResponse> {
  const params: DeliverQuery = {}
  if (quantity !== undefined) params.quantity = quantity
  if (storagePlace) params.storage_place = storagePlace

  return sendIdempotent((config) =>
    webApi.put('/bought-items-allocations/order-item/{order_item_id}/deliver', {
      path: { order_item_id: orderItemId },
      body: rejection
        ? {
            ...rejection,
            damage_noted_on_delivery_note: rejection.damage_noted_on_delivery_note ?? false,
          }
        : null,
      query: Object.keys(params).length ? params : undefined,
      config,
    }),
  )
}
