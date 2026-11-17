import { webApi } from '@/core/api/webRequest'

/** Removes a line; one changed since `expectedEditVersion` was read answers 409. */
export async function removeOrderItem(
  orderId: number,
  orderItemId: number,
  expectedEditVersion: number,
): Promise<void> {
  await webApi.delete('/orders/{order_id}/items/{order_item_id}', {
    path: { order_id: orderId, order_item_id: orderItemId },
    query: { expected_edit_version: expectedEditVersion },
  })
}
