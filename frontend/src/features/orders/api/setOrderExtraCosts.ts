import { webApi } from '@/core/api/webRequest'

import type { OrderExtraCostsUpdateRequest } from '../types/ordersRequest'
import type { OrderResponse } from '../types/ordersResponse'

export async function setOrderExtraCosts(
  id: number,
  payload: OrderExtraCostsUpdateRequest,
): Promise<OrderResponse> {
  return webApi.put('/orders/{order_id}/extra-costs', {
    path: { order_id: id },
    body: payload,
  })
}
