import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function getQuoteRequest(id: number): Promise<QuoteRequestResponse> {
  return webApi.get('/quote-requests/{request_id}', { path: { request_id: id } })
}
