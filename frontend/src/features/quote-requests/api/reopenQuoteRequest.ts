import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

/** Reopens a closed request whose award was voided; `expectedEditVersion` is the one the user saw. */
export async function reopenQuoteRequest(
  id: number,
  expectedEditVersion: number,
): Promise<QuoteRequestResponse> {
  return webApi.post('/quote-requests/{request_id}/reopen', {
    path: { request_id: id },
    query: { expected_edit_version: expectedEditVersion },
  })
}
