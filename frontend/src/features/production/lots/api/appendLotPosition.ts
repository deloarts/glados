import { webApi } from '@/core/api/webRequest'

import type { AppendLotPositionRequest } from '../../types/productionLotsRequest'
import type { LotPositionResponse } from '../../types/productionLotsResponse'

export async function appendLotPosition(
  lotId: number,
  payload: AppendLotPositionRequest,
): Promise<LotPositionResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/positions', {
    path: { lot_id: lotId },
    body: payload,
  }) as Promise<LotPositionResponse>
}
