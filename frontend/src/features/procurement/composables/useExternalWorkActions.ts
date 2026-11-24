import { createOrder, getOrders } from '@/features/orders'
import { assignExternalPosition, unassignExternalPosition } from '@/features/production'
import { DEFAULT_UNIT } from '@/shared/utils/units'

import type { ExternalWorkRow } from '../types/externalWork'

/**
 * The row actions of the external work list that need no dialog. Taking
 * the suggestion puts the position on a draft order of the suggested
 * supplier, the one already open if there is one, so the parts for one
 * supplier collect on one order.
 */
export function useExternalWorkActions() {
  async function draftOrderOf(supplierId: number): Promise<number> {
    const open = await getOrders({ supplier_id: supplierId, status: ['draft'], limit: 1 })
    const existing = open.items[0]
    if (existing) return existing.id
    return (await createOrder({ supplier_id: supplierId })).id
  }

  async function takeSuggestion(row: ExternalWorkRow): Promise<void> {
    if (row.suggested_supplier_id === null) return
    const orderId = await draftOrderOf(row.suggested_supplier_id)
    await assignExternalPosition(row.lot_id, row.position_id, {
      order_id: orderId,
      unit: DEFAULT_UNIT,
    })
  }

  async function removeFromOrder(row: ExternalWorkRow): Promise<void> {
    await unassignExternalPosition(row.lot_id, row.position_id)
  }

  return { takeSuggestion, removeFromOrder }
}
