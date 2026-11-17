import { webApi } from '@/core/api/webRequest'

import type { RecordManufacturingAssessmentRequest } from '../types/productionOrdersRequest'
import type { ManufacturingAssessmentResponse } from '../types/productionOrdersResponse'

export async function recordManufacturingAssessment(
  id: number,
  payload: RecordManufacturingAssessmentRequest,
): Promise<ManufacturingAssessmentResponse> {
  return webApi.post('/production-orders/{production_order_id}/assessment', {
    path: { production_order_id: id },
    body: payload,
  })
}
