import { webApi } from '@/core/api/webRequest'

import type { SupplierUpdateRequest } from '../types/supplierRequest'
import type { SupplierResponse } from '../types/supplierResponse'

export async function updateSupplier(
  supplierId: number,
  payload: SupplierUpdateRequest,
): Promise<SupplierResponse> {
  return webApi.put('/suppliers/{supplier_id}', {
    path: { supplier_id: supplierId },
    body: payload,
  })
}
