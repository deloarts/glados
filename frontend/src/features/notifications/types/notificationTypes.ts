import type { Schemas } from '@/core/api/generated'

/**
 * The backend's own schema is `NotificationResult`, aliased as
 * `NotificationResponse`, the name this feature uses.
 */
export type NotificationResponse = Schemas['NotificationResult']

export type NotificationsResponse = Schemas['NotificationsResponse']
