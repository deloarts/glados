import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type { PdmFileSnapshot, PdmFileSnapshotFilterParams } from '../types/adminSettingsTypes'

/**
 * Paged, filtered list of every watched PDM file and where it stands in the
 * poll -> ingest pipeline, for the admin "PDM files" pending-list tab.
 */
export async function getPdmFiles(
  params?: PdmFileSnapshotFilterParams,
): Promise<PageResponse<PdmFileSnapshot>> {
  // kind and item_kind are narrowed to closed unions, see PdmFileSnapshot.
  return webApi.get('/admin/settings/pdm/files', {
    query: params,
  }) as Promise<PageResponse<PdmFileSnapshot>>
}
