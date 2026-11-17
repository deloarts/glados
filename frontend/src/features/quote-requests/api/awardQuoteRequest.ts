import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestAwardRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestAwardResponse } from '../types/quoteRequestsResponse'

export async function awardQuoteRequest(
  id: number,
  payload: QuoteRequestAwardRequest,
): Promise<QuoteRequestAwardResponse> {
  return sendIdempotent((config) =>
    webApi.post('/quote-requests/{request_id}/award', {
      path: { request_id: id },
      body: payload,
      config,
    }),
  )
}
