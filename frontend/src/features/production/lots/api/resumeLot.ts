import { webApi } from '@/core/api/webRequest'

import type { LotResponse } from '../../types/productionLotsResponse'

export async function resumeLot(id: number): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/{lot_id}/resume', {
    path: { lot_id: id },
  }) as Promise<LotResponse>
}
