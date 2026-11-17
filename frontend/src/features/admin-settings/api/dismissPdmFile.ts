import { webApi } from '@/core/api/webRequest'
import type { PdmFileSnapshot } from '../types/adminSettingsTypes'

/**
 * Dismisses one pending-list row without contacting PDM: marks it skipped
 * and drops any parked ingest payload.
 */
export async function dismissPdmFile(snapshotId: number): Promise<PdmFileSnapshot> {
  // kind and item_kind are narrowed to closed unions, see PdmFileSnapshot.
  return webApi.post('/admin/settings/pdm/files/{snapshot_id}/dismiss', {
    path: { snapshot_id: snapshotId },
  }) as Promise<PdmFileSnapshot>
}
