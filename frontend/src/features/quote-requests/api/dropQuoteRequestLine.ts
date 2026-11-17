import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

/** Gives the line to nobody, or with `restore` takes that back. */
export async function dropQuoteRequestLine(
  id: number,
  lineId: number,
  restore = false,
): Promise<QuoteRequestResponse> {
  const path = { request_id: id, line_id: lineId }
  return restore
    ? webApi.post('/quote-requests/{request_id}/lines/{line_id}/restore', { path })
    : webApi.post('/quote-requests/{request_id}/lines/{line_id}/drop', { path })
}
