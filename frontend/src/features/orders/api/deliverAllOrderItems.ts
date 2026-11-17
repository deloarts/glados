import { sendIdempotent } from '@/core/api/idempotency'
import { webApi } from '@/core/api/webRequest'

import type { OrderItemRejectionRequest } from '../types/ordersRequest'
import type { DeliverAllResponse } from '../types/ordersResponse'

/**
 * Delivers every line that can take a delivery and reports the skipped ones.
 * `damageNoted` records that damage was noted on the carrier's delivery note.
 */
export async function deliverAllOrderItems(
  orderId: number,
  storagePlace?: string,
  rejections?: OrderItemRejectionRequest[],
  deliveryNoteNumber?: string,
  damageNoted?: boolean,
): Promise<DeliverAllResponse> {
  const hasRejections = !!rejections && rejections.length > 0
  return sendIdempotent((config) =>
    webApi.put('/orders/{order_id}/deliver-all-items', {
      path: { order_id: orderId },
      body:
        hasRejections || deliveryNoteNumber || damageNoted
          ? {
              rejections: rejections ?? [],
              ...(deliveryNoteNumber ? { delivery_note_number: deliveryNoteNumber } : {}),
              ...(damageNoted ? { damage_noted_on_delivery_note: true } : {}),
            }
          : null,
      query: storagePlace ? { storage_place: storagePlace } : undefined,
      config,
    }),
  )
}
