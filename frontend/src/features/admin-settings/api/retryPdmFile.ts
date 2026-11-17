import { webApi } from '@/core/api/webRequest'
import type { PdmFileRetryResult } from '../types/adminSettingsTypes'

/**
 * Resets one pending-list row to pending and asks the pdm_sync worker to
 * refresh it on its next tick: the same PdmFileChangeRequested path the
 * poller and the vault add-in's trigger endpoint use. 202 means queued,
 * not done.
 */
export async function retryPdmFile(snapshotId: number): Promise<PdmFileRetryResult> {
  return webApi.post('/admin/settings/pdm/files/{snapshot_id}/retry', {
    path: { snapshot_id: snapshotId },
  })
}
