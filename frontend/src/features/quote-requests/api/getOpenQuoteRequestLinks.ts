import { webApi } from '@/core/api/webRequest'

import type { QueryOf } from '@/core/api/webRequest'
import type { QuoteRequestLinksResponse } from '../types/quoteRequestsResponse'

export async function getOpenQuoteRequestLinks(
  query: QueryOf<'/quote-requests/open-links'>,
): Promise<QuoteRequestLinksResponse> {
  return webApi.get('/quote-requests/open-links', { query })
}
