import { webApi } from '@/core/api/webRequest'

import type { CustomerResponse } from '../types/customerResponse'

export async function archiveCustomer(customerId: number): Promise<CustomerResponse> {
  return webApi.post('/customers/{customer_id}/archive', { path: { customer_id: customerId } })
}
