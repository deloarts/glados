import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { InspectionMethodResponse } from '../types/inspectionMethodResponse'
import type { InspectionMethodFilterParams } from '../types/inspectionMethodRequest'

export async function getInspectionMethods(
  params?: InspectionMethodFilterParams,
): Promise<PageResponse<InspectionMethodResponse>> {
  return webApi.get('/inspection-methods/', {
    query: params,
  })
}
