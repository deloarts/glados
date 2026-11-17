import { webApi } from '@/core/api/webRequest'

import type { LotPositionCompletionResponse } from '../../types/productionLotsResponse'

export async function getLotCompletions(id: number): Promise<LotPositionCompletionResponse[]> {
  return webApi.get('/production-lots/{lot_id}/completions', { path: { lot_id: id } })
}
