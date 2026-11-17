import { webApi } from '@/core/api/webRequest'

import type { SupplierResponse } from '../types/supplierResponse'

export async function restoreSupplier(supplierId: number): Promise<SupplierResponse> {
  return webApi.post('/suppliers/{supplier_id}/restore', {
    path: { supplier_id: supplierId },
  })
}
