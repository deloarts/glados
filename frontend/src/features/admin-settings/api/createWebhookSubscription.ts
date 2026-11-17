import { webApi } from '@/core/api/webRequest'
import type {
  CreatedWebhookSubscription,
  CreateWebhookSubscriptionCommand,
} from '../types/webhookTypes'

/**
 * Creates a webhook subscription. The response contains the HMAC secret,
 * this is the only time it is ever returned, so show it to the user
 * immediately and make clear it cannot be retrieved again.
 */
export async function createWebhookSubscription(
  cmd: CreateWebhookSubscriptionCommand,
): Promise<CreatedWebhookSubscription> {
  return webApi.post('/admin/webhooks/', { body: cmd })
}
