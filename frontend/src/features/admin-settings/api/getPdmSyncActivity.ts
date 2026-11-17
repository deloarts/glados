import { webApi } from '@/core/api/webRequest'
import type { PdmSyncActivity } from '../types/adminSettingsTypes'

/**
 * What the PDM sync is doing right now: a requested synchronisation waiting
 * for the scheduler, the poll run in progress with its live progress, and
 * the newest processed files across every run.
 */
export async function getPdmSyncActivity(): Promise<PdmSyncActivity> {
  // The entries are narrowed to closed unions, see PdmSyncActivity.
  return webApi.get('/admin/settings/pdm/sync-activity') as Promise<PdmSyncActivity>
}
