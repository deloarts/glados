import { webApi } from '@/core/api/webRequest'

import type { LotCreateRequest } from '../types/productionLotsRequest'
import type { LotResponse } from '../types/productionLotsResponse'

export async function createLot(payload: LotCreateRequest): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/', { body: payload }) as Promise<LotResponse>
}
