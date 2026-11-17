import { webApi } from '@/core/api/webRequest'

import type { CustomerCreateRequest } from '../types/customerRequest'
import type { CustomerResponse } from '../types/customerResponse'

export async function createCustomer(payload: CustomerCreateRequest): Promise<CustomerResponse> {
  return webApi.post('/customers/', { body: payload })
}
