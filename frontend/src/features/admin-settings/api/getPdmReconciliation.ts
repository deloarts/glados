import { webApi } from '@/core/api/webRequest'
import type { PdmReconciliationSummary } from '../types/adminSettingsTypes'

/**
 * The latest reconciliation report for the admin reconciliation dialog: the
 * run it came from (null when reconciliation has never run) plus how many
 * files each category's findings stand for.
 */
export async function getPdmReconciliation(): Promise<PdmReconciliationSummary> {
  return webApi.get('/admin/settings/pdm/reconciliation')
}
