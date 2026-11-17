import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

/**
 * Replaces a line for every supplier with a line for another item of its
 * kind; the old line is dropped and the new one takes its demand shares.
 */
export async function substituteQuoteRequestLine(
  id: number,
  lineId: number,
  body: { bought_item_id?: number | null; source_item_id?: number | null; reason?: string | null },
): Promise<QuoteRequestResponse> {
  return webApi.post('/quote-requests/{request_id}/lines/{line_id}/substitute', {
    path: { request_id: id, line_id: lineId },
    body,
  })
}
