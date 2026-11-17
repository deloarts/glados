/**
 * Browser-side row filter for the webhook subscriptions table's event
 * column. A subscription lists the event types it listens to, where "*"
 * stands for every event, so a plain CONTAINS on the array would hide the
 * catch-all subscriptions that do receive the picked event.
 *
 * The match mode is registered with OpenVue's global FilterService when
 * this module is first imported, the same way shared/utils/rowFilterModes
 * registers its range modes.
 */
import { FilterService } from '@openvue/core/api'

export const WEBHOOK_EVENT_MATCH_MODE = 'gladosWebhookEvent'

export function matchesWebhookEvent(value: unknown, filter: unknown): boolean {
  if (filter === null || filter === undefined || filter === '') return true
  if (!Array.isArray(value)) return false
  return value.includes('*') || value.includes(filter)
}

FilterService.register(WEBHOOK_EVENT_MATCH_MODE, matchesWebhookEvent)
