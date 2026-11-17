import { webApi } from '@/core/api/webRequest'
import type { PdmReconcileResult } from '../types/adminSettingsTypes'

/**
 * Queues a reconciliation report (the admin reconciliation dialog's quick
 * and deep buttons): `deep=false` reads only the
 * database, `deep=true` additionally checks every linked file's write-back
 * datacard variables. 202 means queued, not done: the scheduler's next
 * tick (within 60 seconds) runs it before its own poll-interval check.
 * Rejects with 409 when PDM is not enabled and configured.
 */
export async function requestPdmReconciliation(deep: boolean): Promise<PdmReconcileResult> {
  return webApi.post('/admin/settings/pdm/reconcile', { query: { deep } })
}
