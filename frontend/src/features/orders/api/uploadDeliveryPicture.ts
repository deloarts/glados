import { postFile } from '@/core/api/postFile'

import type { OrderFile } from '../types/ordersResponse'

/**
 * Stores a picture of one delivery row, such as a photo of damaged goods, as
 * an order file of the picture category that names the row. Needs only the
 * permission to receive deliveries.
 */
export async function uploadDeliveryPicture(
  orderId: number,
  orderItemId: number,
  deliveryId: number,
  file: File,
): Promise<OrderFile> {
  return postFile('/orders/{order_id}/items/{order_item_id}/deliveries/{delivery_id}/pictures', file, {
    path: { order_id: orderId, order_item_id: orderItemId, delivery_id: deliveryId },
  })
}
