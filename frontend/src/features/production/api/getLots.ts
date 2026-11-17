import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { LotFilterParams } from '../types/productionLotsRequest'
import type { LotSummaryResponse } from '../types/productionLotsResponse'

export async function getLots(params?: LotFilterParams): Promise<PageResponse<LotSummaryResponse>> {
  // The steps are refined to the role union, see LotStepResponse.
  return webApi.get('/production-lots/', {
    query: params,
  }) as Promise<PageResponse<LotSummaryResponse>>
}
