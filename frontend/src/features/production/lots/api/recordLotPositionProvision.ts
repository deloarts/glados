import { webApi } from '@/core/api/webRequest'

import type { RecordLotPositionProvisionRequest } from '../../types/productionLotsRequest'
import type { LotPositionProvisionResponse } from '../../types/productionLotsResponse'

export async function recordLotPositionProvision(
  lotId: number,
  positionId: number,
  payload: RecordLotPositionProvisionRequest,
): Promise<LotPositionProvisionResponse> {
  return webApi.post('/production-lots/{lot_id}/positions/{position_id}/provisions', {
    path: { lot_id: lotId, position_id: positionId },
    body: payload,
  })
}
