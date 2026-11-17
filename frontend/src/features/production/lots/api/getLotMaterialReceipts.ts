import { webApi } from '@/core/api/webRequest'

import type { LotMaterialReceiptResponse } from '../../types/productionLotsResponse'

/** The receipts of the raw material the lot consumes, for its genealogy. */
export async function getLotMaterialReceipts(id: number): Promise<LotMaterialReceiptResponse[]> {
  return webApi.get('/production-lots/{lot_id}/material-receipts', { path: { lot_id: id } })
}
