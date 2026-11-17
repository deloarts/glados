import { webApi } from '@/core/api/webRequest'

import type { ReplaceLotStructureRequest } from '../../types/productionLotsRequest'
import type { LotPositionResponse } from '../../types/productionLotsResponse'

// The step editor's single transactional save: the whole intended
// structure in one request, so a staged edit either lands completely or
// not at all (see the backend's ReplaceLotStructure).
export async function replaceLotStructure(
  lotId: number,
  payload: ReplaceLotStructureRequest,
): Promise<LotPositionResponse[]> {
  return webApi.put('/production-lots/{lot_id}/structure', {
    path: { lot_id: lotId },
    body: payload,
  }) as Promise<LotPositionResponse[]>
}
