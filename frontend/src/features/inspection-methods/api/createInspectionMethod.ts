import { webApi } from '@/core/api/webRequest'

import type { InspectionMethodCreateRequest } from '../types/inspectionMethodRequest'
import type { InspectionMethodResponse } from '../types/inspectionMethodResponse'

export async function createInspectionMethod(
  payload: InspectionMethodCreateRequest,
): Promise<InspectionMethodResponse> {
  return webApi.post('/inspection-methods/', { body: payload })
}
