import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function removeQuoteRequestSupplier(
  id: number,
  rowId: number,
): Promise<QuoteRequestResponse> {
  return webApi.delete('/quote-requests/{request_id}/suppliers/{row_id}', {
    path: { request_id: id, row_id: rowId },
  })
}
