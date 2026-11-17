import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { RecordProductionOrderCompletionRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

export async function recordProductionOrderCompletion(
  id: number,
  payload: RecordProductionOrderCompletionRequest,
): Promise<ProductionOrderResponse> {
  return sendIdempotent((config) =>
    webApi.post('/production-orders/{production_order_id}/completions', {
      path: { production_order_id: id },
      body: payload,
      config,
    }),
  )
}
