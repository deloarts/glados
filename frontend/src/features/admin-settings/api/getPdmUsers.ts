import { webApi } from '@/core/api/webRequest'
import type { PdmUser } from '../types/adminSettingsTypes'

/**
 * Vault users cross-referenced against Glados users (linked or proposed),
 * for the "Match PDM Users" dialog.
 */
export async function getPdmUsers(): Promise<PdmUser[]> {
  return webApi.get('/admin/settings/pdm/users')
}
