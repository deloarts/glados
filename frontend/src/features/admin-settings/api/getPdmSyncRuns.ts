import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type { PdmSyncRun, PdmSyncRunFilterParams } from '../types/adminSettingsTypes'

/**
 * Paged, newest-first list of the PDM sync run log (poll ticks and single-
 * file refreshes) for the admin sync log dialog's runs table.
 */
export async function getPdmSyncRuns(
  params?: PdmSyncRunFilterParams,
): Promise<PageResponse<PdmSyncRun>> {
  return webApi.get('/admin/settings/pdm/runs', {
    query: params,
  })
}
