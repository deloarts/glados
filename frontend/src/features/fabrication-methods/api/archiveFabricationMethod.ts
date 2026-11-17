import { webApi } from '@/core/api/webRequest'

import type { FabricationMethodResponse } from '../types/fabricationMethodResponse'

export async function archiveFabricationMethod(methodId: number): Promise<FabricationMethodResponse> {
  return webApi.post('/fabrication-methods/{fabrication_method_id}/archive', {
    path: { fabrication_method_id: methodId },
  })
}
