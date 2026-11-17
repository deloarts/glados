import { webApi } from '@/core/api/webRequest'

import type { FabricationMethodCreateRequest } from '../types/fabricationMethodRequest'
import type { FabricationMethodResponse } from '../types/fabricationMethodResponse'

export async function createFabricationMethod(
  payload: FabricationMethodCreateRequest,
): Promise<FabricationMethodResponse> {
  return webApi.post('/fabrication-methods/', {
    body: payload,
  })
}
