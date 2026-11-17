import { webApi } from '@/core/api/webRequest'

import type { AddLotStepRequest } from '../../types/productionLotsRequest'
import type { LotStepResponse } from '../../types/productionLotsResponse'

export async function addLotStep(
  lotId: number,
  payload: AddLotStepRequest,
): Promise<LotStepResponse> {
  // The step is refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/steps', {
    path: { lot_id: lotId },
    body: payload,
  }) as Promise<LotStepResponse>
}
