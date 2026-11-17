import { webApi } from '@/core/api/webRequest'

import type { OfferSaveRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function saveQuoteRequestOffer(
  id: number,
  rowId: number,
  payload: OfferSaveRequest,
): Promise<QuoteRequestResponse> {
  return webApi.put('/quote-requests/{request_id}/suppliers/{row_id}/offer', {
    path: { request_id: id, row_id: rowId },
    body: payload,
  })
}
