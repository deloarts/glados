import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestUpdateRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function updateQuoteRequest(
  id: number,
  payload: QuoteRequestUpdateRequest,
): Promise<QuoteRequestResponse> {
  return webApi.put('/quote-requests/{request_id}', { path: { request_id: id }, body: payload })
}
