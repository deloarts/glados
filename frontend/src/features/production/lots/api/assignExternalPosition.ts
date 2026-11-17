import { webApi } from '@/core/api/webRequest'

import type { AssignExternalPositionRequest } from '../../types/productionLotsRequest'
import type { LotPositionResponse } from '../../types/productionLotsResponse'

export async function assignExternalPosition(
  lotId: number,
  positionId: number,
  payload: AssignExternalPositionRequest,
): Promise<LotPositionResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/positions/{position_id}/assign', {
    path: { lot_id: lotId, position_id: positionId },
    body: payload,
  }) as Promise<LotPositionResponse>
}
