import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { QuoteRequestFilterParams } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function getQuoteRequests(
  params?: QuoteRequestFilterParams,
): Promise<PageResponse<QuoteRequestResponse>> {
  return webApi.get('/quote-requests/', { query: params })
}
