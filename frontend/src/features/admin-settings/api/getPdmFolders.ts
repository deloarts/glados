import { webApi } from '@/core/api/webRequest'
import type { PdmFolder } from '../types/adminSettingsTypes'

/**
 * Proxies one level of the SOLIDWORKS PDM vault's folder tree (subfolders
 * only) for PdmFolderPickerDialog's drill-down. `parentId` defaults to 1,
 * the vault root, on the backend when omitted.
 */
export async function getPdmFolders(parentId: number): Promise<PdmFolder[]> {
  return webApi.get('/admin/settings/pdm/folders', { query: { parent_id: parentId } })
}
