import { dateToParam } from '@/core/utils/dates'

import type { WebhookDeliveriesParams } from '../api/getWebhookDeliveries'

export type WebhookDeliveryOutcome = 'success' | 'failed'

/** The deliveries dialog's row filter values, one per filterable column. */
export interface WebhookDeliveryFilterValues {
  outcome: WebhookDeliveryOutcome | null
  eventType: string | null
  attemptedFrom: Date | null
  attemptedTo: Date | null
}

/**
 * Turns the deliveries dialog's row filters into the request params of
 * GET /admin/webhooks/{id}/deliveries. Empty filters are left out entirely,
 * so an unfiltered request carries only the page.
 */
export function buildWebhookDeliveryParams(
  page: { skip: number; limit: number },
  filters: WebhookDeliveryFilterValues,
): WebhookDeliveriesParams {
  const params: WebhookDeliveriesParams = { skip: page.skip, limit: page.limit }

  if (filters.outcome) params.success = filters.outcome === 'success'
  if (filters.eventType) params.event_type = filters.eventType
  const from = dateToParam(filters.attemptedFrom)
  if (from) params.attempted_from = from
  const to = dateToParam(filters.attemptedTo)
  if (to) params.attempted_to = to

  return params
}
