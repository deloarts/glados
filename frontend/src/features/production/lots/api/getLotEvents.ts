import { webApi } from '@/core/api/webRequest'

import type { LotEventResponse } from '../../types/productionLotsResponse'

export async function getLotEvents(id: number): Promise<LotEventResponse[]> {
  return webApi.get('/production-lots/{lot_id}/events', {
    path: { lot_id: id },
  })
}
