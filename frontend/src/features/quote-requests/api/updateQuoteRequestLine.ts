import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestLineUpdateRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function updateQuoteRequestLine(
  id: number,
  lineId: number,
  payload: QuoteRequestLineUpdateRequest,
): Promise<QuoteRequestResponse> {
  return webApi.put('/quote-requests/{request_id}/lines/{line_id}', {
    path: { request_id: id, line_id: lineId },
    body: payload,
  })
}
