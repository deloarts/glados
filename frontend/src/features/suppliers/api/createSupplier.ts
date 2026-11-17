import { webApi } from '@/core/api/webRequest'

import type { SupplierCreateRequest } from '../types/supplierRequest'
import type { SupplierResponse } from '../types/supplierResponse'

export async function createSupplier(payload: SupplierCreateRequest): Promise<SupplierResponse> {
  return webApi.post('/suppliers/', { body: payload })
}
