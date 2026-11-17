import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { FabricationMethodResponse } from '../types/fabricationMethodResponse'
import type { FabricationMethodFilterParams } from '../types/fabricationMethodRequest'

export async function getFabricationMethods(
  params?: FabricationMethodFilterParams,
): Promise<PageResponse<FabricationMethodResponse>> {
  return webApi.get('/fabrication-methods/', {
    query: params,
  })
}
