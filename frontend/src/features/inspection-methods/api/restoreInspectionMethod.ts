import { webApi } from '@/core/api/webRequest'

import type { InspectionMethodResponse } from '../types/inspectionMethodResponse'

export async function restoreInspectionMethod(methodId: number): Promise<InspectionMethodResponse> {
  return webApi.post('/inspection-methods/{inspection_method_id}/restore', {
    path: { inspection_method_id: methodId },
  })
}
