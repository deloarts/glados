import { webApi } from '@/core/api/webRequest'

import type { CustomerUpdateRequest } from '../types/customerRequest'
import type { CustomerResponse } from '../types/customerResponse'

export async function updateCustomer(
  customerId: number,
  payload: CustomerUpdateRequest,
): Promise<CustomerResponse> {
  return webApi.put('/customers/{customer_id}', {
    path: { customer_id: customerId },
    body: payload,
  })
}
