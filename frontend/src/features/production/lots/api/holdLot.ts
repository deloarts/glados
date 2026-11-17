import { webApi } from '@/core/api/webRequest'

import type { HoldLotRequest } from '../../types/productionLotsRequest'
import type { LotResponse } from '../../types/productionLotsResponse'

export async function holdLot(id: number, payload: HoldLotRequest): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/hold', {
    path: { lot_id: id },
    body: payload,
  }) as Promise<LotResponse>
}
