import { webApi } from '@/core/api/webRequest'

import type { CompleteLotRequest } from '../types/productionLotsRequest'
import type { LotResponse } from '../types/productionLotsResponse'

export async function completeLot(
  id: number,
  payload: CompleteLotRequest,
): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/complete', {
    path: { lot_id: id },
    body: payload,
  }) as Promise<LotResponse>
}
