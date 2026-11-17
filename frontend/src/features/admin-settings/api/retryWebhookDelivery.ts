import { webApi } from '@/core/api/webRequest'
import type { WebhookDelivery } from '../types/webhookTypes'

/** Re-sends the stored payload and returns the newly appended log entry. */
export async function retryWebhookDelivery(deliveryId: number): Promise<WebhookDelivery> {
  return webApi.post('/admin/webhooks/deliveries/{delivery_id}/retry', {
    path: { delivery_id: deliveryId },
  })
}
