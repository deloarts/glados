import { webApi } from '@/core/api/webRequest'

import type { OrderSupplierOrderNumbersUpdateRequest } from '../types/ordersRequest'
import type { OrderResponse } from '../types/ordersResponse'

export async function setOrderSupplierOrderNumbers(
  id: number,
  payload: OrderSupplierOrderNumbersUpdateRequest,
): Promise<OrderResponse> {
  return webApi.put('/orders/{order_id}/supplier-order-numbers', {
    path: { order_id: id },
    body: payload,
  })
}
