import { webApi } from '@/core/api/webRequest'
import type { SupplierResponse } from '../types/supplierResponse'

export async function getSupplier(id: number): Promise<SupplierResponse> {
  return webApi.get('/suppliers/{supplier_id}', {
    path: { supplier_id: id },
  })
}
