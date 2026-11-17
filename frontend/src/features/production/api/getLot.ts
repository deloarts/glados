import { webApi } from '@/core/api/webRequest'

import type { LotResponse } from '../types/productionLotsResponse'

export async function getLot(id: number): Promise<LotResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.get('/production-lots/{lot_id}', { path: { lot_id: id } }) as Promise<LotResponse>
}
