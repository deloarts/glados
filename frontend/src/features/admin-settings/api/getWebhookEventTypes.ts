import { webApi } from '@/core/api/webRequest'

/** All event type names a webhook subscription can listen to ("*" means all). */
export async function getWebhookEventTypes(): Promise<string[]> {
  return webApi.get('/admin/webhooks/event-types')
}
