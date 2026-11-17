import { webApi } from '@/core/api/webRequest'

import type { FabricationMethodUpdateRequest } from '../types/fabricationMethodRequest'
import type { FabricationMethodResponse } from '../types/fabricationMethodResponse'

export async function updateFabricationMethod(
  methodId: number,
  payload: FabricationMethodUpdateRequest,
): Promise<FabricationMethodResponse> {
  return webApi.put('/fabrication-methods/{fabrication_method_id}', {
    path: { fabrication_method_id: methodId },
    body: payload,
  })
}
