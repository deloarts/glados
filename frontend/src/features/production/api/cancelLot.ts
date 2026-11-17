import { webApi } from '@/core/api/webRequest'

import type { CancelLotRequest } from '../types/productionLotsRequest'
import type { LotResponse } from '../types/productionLotsResponse'

export async function cancelLot(id: number, payload: CancelLotRequest): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/cancel', {
    path: { lot_id: id },
    body: payload,
  }) as Promise<LotResponse>
}
