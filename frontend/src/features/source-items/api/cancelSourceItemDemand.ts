import { webApi } from '@/core/api/webRequest'

import type { SourceItemDemandResponse } from '../types/sourceItemDemandsResponse'

/**
 * Cancels a raw material demand. `cancelLot` is the choice the server asks
 * for while the demand still feeds a lot that has not ended: cancel the lot
 * too, or cancel only the demand and leave the lot waiting on raw material.
 */
export async function cancelSourceItemDemand(
  demandId: number,
  cancelLot: boolean,
): Promise<SourceItemDemandResponse> {
  return webApi.post('/source-item-demands/{demand_id}/cancel', {
    path: { demand_id: demandId },
    query: { cancel_lot: cancelLot },
  })
}

/** The same cancel through the status route, which manage:demand_items opens. */
export async function cancelSourceItemDemandByStatus(
  demandId: number,
  cancelLot: boolean,
): Promise<SourceItemDemandResponse> {
  return webApi.put('/source-item-demands/{demand_id}/status', {
    path: { demand_id: demandId },
    query: { new_status: 'canceled', cancel_lot: cancelLot },
    body: null,
  })
}
