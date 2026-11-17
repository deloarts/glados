import { webApi } from '@/core/api/webRequest'
import type { PdmOperation } from '../types/adminSettingsTypes'

/**
 * Lists the SOLIDWORKS PDM Web API operation catalogue for the admin API
 * console. Read-only against the backend's in-process catalogue, no call
 * to the vault itself is made.
 */
export async function getPdmOperations(): Promise<PdmOperation[]> {
  return webApi.get('/admin/settings/pdm/operations')
}
