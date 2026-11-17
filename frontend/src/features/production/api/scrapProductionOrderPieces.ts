import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { ScrapProductionPiecesRequest } from '../types/productionOrdersRequest'
import type { ScrapPiecesResponse } from '../types/productionLotsResponse'

export async function scrapProductionOrderPieces(
  id: number,
  payload: ScrapProductionPiecesRequest,
): Promise<ScrapPiecesResponse> {
  // The steps are refined to the role union, see LotStepResponse.
  return sendIdempotent(
    (config) =>
      webApi.post('/production-orders/{production_order_id}/scrap', {
        path: { production_order_id: id },
        body: payload,
        config,
      }) as Promise<ScrapPiecesResponse>,
  )
}
