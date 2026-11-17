import { webApi } from '@/core/api/webRequest'

import type { SwitchLotMaterialSourceRequest } from '../../types/productionLotsRequest'
import type { LotResponse } from '../../types/productionLotsResponse'

export async function switchLotMaterialSource(
  lotId: number,
  payload: SwitchLotMaterialSourceRequest,
): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.put('/production-lots/{lot_id}/material-source', {
    path: { lot_id: lotId },
    body: payload,
  }) as Promise<LotResponse>
}
