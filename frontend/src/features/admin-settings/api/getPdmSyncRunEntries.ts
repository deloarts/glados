import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type { PdmSyncRunEntry, PdmSyncRunEntryFilterParams } from '../types/adminSettingsTypes'

/**
 * Paged, optionally action-filtered list of one sync run's per-file
 * entries, for the "View sync log" dialog's entries table shown on
 * selecting a run.
 */
export async function getPdmSyncRunEntries(
  runId: number,
  params?: PdmSyncRunEntryFilterParams,
): Promise<PageResponse<PdmSyncRunEntry>> {
  // kind and action are narrowed to closed unions, see PdmSyncRunEntry.
  return webApi.get('/admin/settings/pdm/runs/{run_id}/entries', {
    path: { run_id: runId },
    query: params,
  }) as Promise<PageResponse<PdmSyncRunEntry>>
}
