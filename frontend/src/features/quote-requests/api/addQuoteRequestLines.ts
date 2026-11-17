import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestLineRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function addQuoteRequestLines(
  id: number,
  lines: QuoteRequestLineRequest[],
): Promise<QuoteRequestResponse> {
  return webApi.post('/quote-requests/{request_id}/lines', {
    path: { request_id: id },
    body: { lines },
  })
}
