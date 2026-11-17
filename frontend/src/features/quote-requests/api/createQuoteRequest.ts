import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestCreateRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function createQuoteRequest(
  payload: QuoteRequestCreateRequest,
): Promise<QuoteRequestResponse> {
  return webApi.post('/quote-requests/', { body: payload })
}
