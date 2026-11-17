import { webApi } from '@/core/api/webRequest'

import type { RejectLotSourceRequest } from '../../types/productionLotsRequest'
import type { LotResponse } from '../../types/productionLotsResponse'

export async function rejectLotSource(id: number, payload: RejectLotSourceRequest): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/source/reject', {
    path: { lot_id: id },
    body: payload,
  }) as Promise<LotResponse>
}
