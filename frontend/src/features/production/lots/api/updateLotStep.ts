import { webApi } from '@/core/api/webRequest'

import type { UpdateLotStepRequest } from '../../types/productionLotsRequest'
import type { LotStepResponse } from '../../types/productionLotsResponse'

export async function updateLotStep(
  lotId: number,
  stepId: number,
  payload: UpdateLotStepRequest,
): Promise<LotStepResponse> {
  // The step is refined to the role union, see LotStepResponse.
  return webApi.patch('/production-lots/{lot_id}/steps/{step_id}', {
    path: { lot_id: lotId, step_id: stepId },
    body: payload,
  }) as Promise<LotStepResponse>
}
