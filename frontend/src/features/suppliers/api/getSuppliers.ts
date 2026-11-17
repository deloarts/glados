import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { SupplierFilterParams } from '../types/supplierRequest'
import type { SupplierResponse } from '../types/supplierResponse'

export async function getSuppliers(
  params?: SupplierFilterParams,
): Promise<PageResponse<SupplierResponse>> {
  return webApi.get('/suppliers/', { query: params })
}
