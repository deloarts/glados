import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { CustomerFilterParams } from '../types/customerRequest'
import type { CustomerResponse } from '../types/customerResponse'

export async function getCustomers(
  params?: CustomerFilterParams,
): Promise<PageResponse<CustomerResponse>> {
  return webApi.get('/customers/', { query: params })
}
