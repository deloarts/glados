import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { ScrapLotPiecesRequest } from '../types/productionLotsRequest'
import type { ScrapPiecesResponse } from '../types/productionLotsResponse'

export async function scrapLotPieces(
  id: number,
  payload: ScrapLotPiecesRequest,
): Promise<ScrapPiecesResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return sendIdempotent(
    (config) =>
      webApi.post('/production-lots/{lot_id}/scrap', {
        path: { lot_id: id },
        body: payload,
        config,
      }) as Promise<ScrapPiecesResponse>,
  )
}
