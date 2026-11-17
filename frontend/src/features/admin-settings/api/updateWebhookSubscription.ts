import { webApi } from '@/core/api/webRequest'
import type { UpdateWebhookSubscriptionCommand, WebhookSubscription } from '../types/webhookTypes'

export async function updateWebhookSubscription(
  subscriptionId: number,
  cmd: UpdateWebhookSubscriptionCommand,
): Promise<WebhookSubscription> {
  return webApi.put('/admin/webhooks/{subscription_id}', {
    path: { subscription_id: subscriptionId },
    body: cmd,
  })
}
