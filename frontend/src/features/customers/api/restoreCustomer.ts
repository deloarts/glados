import { webApi } from '@/core/api/webRequest'

import type { CustomerResponse } from '../types/customerResponse'

export async function restoreCustomer(customerId: number): Promise<CustomerResponse> {
  return webApi.post('/customers/{customer_id}/restore', { path: { customer_id: customerId } })
}
