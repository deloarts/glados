import { webApi } from '@/core/api/webRequest'

import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

export async function addQuoteRequestSuppliers(
  id: number,
  supplierIds: number[],
): Promise<QuoteRequestResponse> {
  return webApi.post('/quote-requests/{request_id}/suppliers', {
    path: { request_id: id },
    body: { supplier_ids: supplierIds },
  })
}
