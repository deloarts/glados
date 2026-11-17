import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

/** Closes or cancels the request; `expectedEditVersion` is the one the user saw. */
export async function endQuoteRequest(
  id: number,
  action: 'close' | 'cancel',
  expectedEditVersion: number,
): Promise<QuoteRequestResponse> {
  const options = {
    path: { request_id: id },
    query: { expected_edit_version: expectedEditVersion },
  }
  return action === 'close'
    ? webApi.post('/quote-requests/{request_id}/close', options)
    : webApi.post('/quote-requests/{request_id}/cancel', options)
}
