import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function removeQuoteRequestLine(
  id: number,
  lineId: number,
): Promise<QuoteRequestResponse> {
  return webApi.delete('/quote-requests/{request_id}/lines/{line_id}', {
    path: { request_id: id, line_id: lineId },
  })
}
