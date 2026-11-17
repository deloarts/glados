import { webApi } from '@/core/api/webRequest'

import { API_MAX_PAGE_SIZE } from '@/core/constants/table'

/** The orders of a supplier an award may add its lines to: drafts and partially ordered orders, whose unordered lines stay open to the buyer. */
export async function getSupplierDraftOrders(
  supplierId: number,
): Promise<{ id: number; order_number: string }[]> {
  const page = await webApi.get('/orders/', {
    query: { supplier_id: supplierId, status: ['draft', 'partially_ordered'], limit: API_MAX_PAGE_SIZE },
  })
  return page.items
    .filter((order) => order.canceled_at === null)
    .map((order) => ({ id: order.id, order_number: order.order_number }))
}
