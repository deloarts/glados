import type { Schemas } from '@/core/api/generated'

/**
 * The backend's own schema is `WebhookSubscriptionResult`, aliased as
 * `WebhookSubscription`, the name this feature uses.
 */
export type WebhookSubscription = Schemas['WebhookSubscriptionResult']

/**
 * Returned only by the create call, the single moment the secret is
 * visible. The backend's own schema is `CreatedWebhookSubscriptionResult`.
 */
export type CreatedWebhookSubscription = Schemas['CreatedWebhookSubscriptionResult']

export type CreateWebhookSubscriptionCommand = Schemas['WebhookSubscriptionCreateRequest']

export type UpdateWebhookSubscriptionCommand = Schemas['WebhookSubscriptionUpdateRequest']

/**
 * The backend's own schema is `WebhookDeliveryResult`, aliased as
 * `WebhookDelivery`, the name this feature uses.
 */
export type WebhookDelivery = Schemas['WebhookDeliveryResult']
