import { webApi } from '@/core/api/webRequest'

import type { LotUpdateRequest } from '../types/productionLotsRequest'
import type { LotResponse } from '../types/productionLotsResponse'

export async function updateLot(id: number, payload: LotUpdateRequest): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.patch('/production-lots/{lot_id}', {
    path: { lot_id: id },
    body: payload,
  }) as Promise<LotResponse>
}
