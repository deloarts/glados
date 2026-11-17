import { webApi } from '@/core/api/webRequest'

import type { LotDemandResponse } from '../../types/productionLotsResponse'

export async function getLotDemands(id: number): Promise<LotDemandResponse[]> {
  // The items' processes are refined to the role union, see MadeItemProcessResponse.
  return webApi.get('/production-lots/{lot_id}/demands', {
    path: { lot_id: id },
  }) as Promise<LotDemandResponse[]>
}
