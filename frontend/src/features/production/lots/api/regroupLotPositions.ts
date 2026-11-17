import { webApi } from '@/core/api/webRequest'

import type { LotPositionResponse } from '../../types/productionLotsResponse'

export async function regroupLotPositions(
  lotId: number,
  groups: number[][],
): Promise<LotPositionResponse[]> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.put('/production-lots/{lot_id}/positions', {
    path: { lot_id: lotId },
    body: { groups },
  }) as Promise<LotPositionResponse[]>
}
