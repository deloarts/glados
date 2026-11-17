import { webApi } from '@/core/api/webRequest'

import type { LotStepResponse } from '../../types/productionLotsResponse'

export async function reorderLotSteps(
  lotId: number,
  orderedStepIds: number[],
): Promise<LotStepResponse[]> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.put('/production-lots/{lot_id}/steps/reorder', {
    path: { lot_id: lotId },
    body: { ordered_step_ids: orderedStepIds },
  }) as Promise<LotStepResponse[]>
}
