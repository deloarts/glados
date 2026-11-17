import { webApi } from '@/core/api/webRequest'
import type { WebhookSubscription } from '../types/webhookTypes'

export async function getWebhookSubscriptions(): Promise<WebhookSubscription[]> {
  return webApi.get('/admin/webhooks/')
}
