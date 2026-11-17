import { webApi } from '@/core/api/webRequest'

import type { LotPositionBalanceResponse } from '../../types/productionLotsResponse'

/** Where the pieces of each position of the lot went. */
export async function getLotPositionBalances(id: number): Promise<LotPositionBalanceResponse[]> {
  return webApi.get('/production-lots/{lot_id}/position-balances', { path: { lot_id: id } })
}
