import { webApi } from '@/core/api/webRequest'

import type { SupplierResponse } from '../types/supplierResponse'

export async function archiveSupplier(supplierId: number): Promise<SupplierResponse> {
  return webApi.post('/suppliers/{supplier_id}/archive', {
    path: { supplier_id: supplierId },
  })
}
