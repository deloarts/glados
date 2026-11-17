import type { PageResponse } from '@/core/api/types'
import type { WebhookDelivery } from '../types/webhookTypes'
import { webApi, type QueryOf } from '@/core/api/webRequest'

export type WebhookDeliveriesParams = QueryOf<'/admin/webhooks/{subscription_id}/deliveries'>

export async function getWebhookDeliveries(
  subscriptionId: number,
  params?: WebhookDeliveriesParams,
): Promise<PageResponse<WebhookDelivery>> {
  return webApi.get('/admin/webhooks/{subscription_id}/deliveries', {
    path: { subscription_id: subscriptionId },
    query: params,
  })
}
