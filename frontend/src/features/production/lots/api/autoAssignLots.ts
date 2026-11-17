import { webApi } from '@/core/api/webRequest'

import type { LotResponse } from '../../types/productionLotsResponse'

export async function autoAssignLots(): Promise<LotResponse[]> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.post('/production-lots/auto-assign') as Promise<LotResponse[]>
}
