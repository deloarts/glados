import { dateToParam } from '@/core/utils/dates'

import type { SecurityEventsParams } from '../api/getSecurityEvents'
import type { SecurityEventOutcome, SecurityEventType } from '../types/adminSettingsTypes'

/** The Security log tab's row filter values, one per filterable column. */
export interface SecurityEventFilterValues {
  userId: number | null
  eventType: SecurityEventType | null
  outcome: SecurityEventOutcome | null
  occurredFrom: Date | null
  occurredTo: Date | null
}

/**
 * Turns the Security log tab's row filters into the request params of
 * GET /admin/settings/security-events. Empty filters are left out entirely,
 * so an unfiltered request carries only the page.
 */
export function buildSecurityEventParams(
  page: { skip: number; limit: number },
  filters: SecurityEventFilterValues,
): SecurityEventsParams {
  const params: SecurityEventsParams = { skip: page.skip, limit: page.limit }

  if (filters.userId != null) params.user_id = filters.userId
  if (filters.eventType) params.event_type = filters.eventType
  if (filters.outcome) params.outcome = filters.outcome
  const from = dateToParam(filters.occurredFrom)
  if (from) params.occurred_from = from
  const to = dateToParam(filters.occurredTo)
  if (to) params.occurred_to = to

  return params
}
