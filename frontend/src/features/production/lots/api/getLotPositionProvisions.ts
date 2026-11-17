import { webApi } from '@/core/api/webRequest'

import type { LotPositionProvisionResponse } from '../../types/productionLotsResponse'

export async function getLotPositionProvisions(
  lotId: number,
  positionId: number,
): Promise<LotPositionProvisionResponse[]> {
  return webApi.get('/production-lots/{lot_id}/positions/{position_id}/provisions', {
    path: { lot_id: lotId, position_id: positionId },
  })
}
