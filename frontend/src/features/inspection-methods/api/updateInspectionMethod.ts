import { webApi } from '@/core/api/webRequest'

import type { InspectionMethodUpdateRequest } from '../types/inspectionMethodRequest'
import type { InspectionMethodResponse } from '../types/inspectionMethodResponse'

export async function updateInspectionMethod(
  methodId: number,
  payload: InspectionMethodUpdateRequest,
): Promise<InspectionMethodResponse> {
  return webApi.put('/inspection-methods/{inspection_method_id}', {
    path: { inspection_method_id: methodId },
    body: payload,
  })
}
