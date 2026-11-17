import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function markQuoteRequestSupplierSent(
  id: number,
  rowId: number,
): Promise<QuoteRequestResponse> {
  return webApi.post('/quote-requests/{request_id}/suppliers/{row_id}/sent', {
    path: { request_id: id, row_id: rowId },
  })
}
