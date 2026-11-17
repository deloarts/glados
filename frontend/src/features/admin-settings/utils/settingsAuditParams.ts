import { dateToParam } from '@/core/utils/dates'

import type { SettingsAuditParams } from '../api/getSettingsAudit'

/** The Audit tab's row filter values, one per filterable column. */
export interface SettingsAuditFilterValues {
  changedById: number | null
  settingsDomain: string | null
  summary: string | null
  changedFrom: Date | null
  changedTo: Date | null
}

function text(value: string | null): string | undefined {
  const trimmed = value?.trim()
  return trimmed ? trimmed : undefined
}

/**
 * Turns the Audit tab's row filters into the request params of
 * GET /admin/settings/audit. Empty filters are left out entirely, so an
 * unfiltered request carries only the page.
 */
export function buildSettingsAuditParams(
  page: { skip: number; limit: number },
  filters: SettingsAuditFilterValues,
): SettingsAuditParams {
  const params: SettingsAuditParams = { skip: page.skip, limit: page.limit }

  if (filters.changedById != null) params.changed_by_id = filters.changedById
  if (filters.settingsDomain) params.settings_domain = filters.settingsDomain
  const summary = text(filters.summary)
  if (summary) params.summary = summary
  const from = dateToParam(filters.changedFrom)
  if (from) params.changed_from = from
  const to = dateToParam(filters.changedTo)
  if (to) params.changed_to = to

  return params
}
