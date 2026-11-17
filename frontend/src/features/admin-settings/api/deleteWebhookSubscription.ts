import { webApi } from '@/core/api/webRequest'

export async function deleteWebhookSubscription(subscriptionId: number): Promise<void> {
  await webApi.delete('/admin/webhooks/{subscription_id}', {
    path: { subscription_id: subscriptionId },
  })
}
